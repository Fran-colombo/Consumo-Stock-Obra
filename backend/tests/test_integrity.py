import threading
from decimal import Decimal

from app.core.errors import AppError
from app.models.entities import User
from app.services.consumption import register_consumption


def auth(client, username="admin", password="admin-pass-123"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def unit_id(client, headers, code):
    rows = client.get("/api/units", headers=headers).json()
    return next(row["id"] for row in rows if row["code"] == code)


def build_world(client, headers, code="OBRA-A"):
    m3 = unit_id(client, headers, "m3")
    unit = unit_id(client, headers, "u")
    work = client.post(
        "/api/works",
        headers=headers,
        json={"name": "Obra de prueba", "code": code, "address": "Calle 1", "status": "ACTIVA"},
    )
    assert work.status_code == 201, work.text
    work = work.json()
    rubric = client.post(
        "/api/rubrics",
        headers=headers,
        json={"name": "Contrapiso", "code": f"R-{code}", "description": "Rubro de prueba"},
    ).json()
    material = client.post(
        "/api/materials",
        headers=headers,
        json={"name": "Cemento", "code": f"CEM-{code}", "unit_id": unit},
    ).json()
    task = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "work_id": work["id"],
            "rubric_id": rubric["id"],
            "name": "Ejecución de contrapiso",
            "unit_id": m3,
            "planned_qty": "20",
            "status": "EN_CURSO",
        },
    ).json()
    supplier = client.post("/api/suppliers", headers=headers, json={"name": f"Proveedor {code}"}).json()
    return {
        "work": work,
        "rubric": rubric,
        "material": material,
        "task": task,
        "supplier": supplier,
        "m3": m3,
        "unit": unit,
    }


def test_receipt_increases_stock_and_order_without_receipt_does_not(client):
    headers = auth(client)
    world = build_world(client, headers)
    before = client.get(
        "/api/stock/available",
        headers=headers,
        params={"material_id": world["material"]["id"], "location_id": world["work"]["location_id"]},
    ).json()
    assert before["on_hand"] == "0.0000"
    order = client.post(
        "/api/purchase-orders",
        headers=headers,
        json={
            "supplier_id": world["supplier"]["id"],
            "destination_location_id": world["work"]["location_id"],
            "work_id": world["work"]["id"],
            "items": [{"material_id": world["material"]["id"], "quantity": "100"}],
        },
    ).json()
    confirmed = client.post(f"/api/purchase-orders/{order['id']}/confirm", headers=headers)
    assert confirmed.status_code == 200
    unchanged = client.get(
        "/api/stock/available",
        headers=headers,
        params={"material_id": world["material"]["id"], "location_id": world["work"]["location_id"]},
    ).json()
    assert unchanged["on_hand"] == "0.0000"
    assert confirmed.json()["items"][0]["qty_pending"] == "100.0000"
    first = client.post(
        f"/api/purchase-orders/{order['id']}/receipts",
        headers={**headers, "Idempotency-Key": "rec-1"},
        json={
            "location_id": world["work"]["location_id"],
            "items": [{"purchase_order_item_id": order["items"][0]["id"], "quantity": "60"}],
        },
    )
    assert first.status_code == 201, first.text
    detail = client.get(f"/api/purchase-orders/{order['id']}", headers=headers).json()
    assert detail["status"] == "PARCIAL"
    assert detail["items"][0]["qty_received"] == "60.0000"
    assert detail["items"][0]["qty_pending"] == "40.0000"
    stock = client.get(
        "/api/stock/available",
        headers=headers,
        params={"material_id": world["material"]["id"], "location_id": world["work"]["location_id"]},
    ).json()
    assert stock["on_hand"] == "60.0000"
    second = client.post(
        f"/api/purchase-orders/{order['id']}/receipts",
        headers={**headers, "Idempotency-Key": "rec-2"},
        json={
            "location_id": world["work"]["location_id"],
            "items": [{"purchase_order_item_id": order["items"][0]["id"], "quantity": "40"}],
        },
    )
    assert second.status_code == 201, second.text
    detail = client.get(f"/api/purchase-orders/{order['id']}", headers=headers).json()
    assert detail["status"] == "RECIBIDA"
    assert detail["items"][0]["qty_pending"] == "0.0000"
    stock = client.get(
        "/api/stock/available",
        headers=headers,
        params={"material_id": world["material"]["id"], "location_id": world["work"]["location_id"]},
    ).json()
    assert stock["on_hand"] == "100.0000"


def test_consumption_decreases_stock_and_rejects_excess_and_foreign_task(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-B")
    other = build_world(client, headers, "OBRA-C")
    _receive(client, headers, world, "30")
    missing = client.post("/api/consumptions", headers=headers, json={})
    assert missing.status_code == 401 or missing.status_code == 422
    denied = client.post(
        "/api/consumptions",
        json={
            "work_id": world["work"]["id"],
            "task_id": world["task"]["id"],
            "location_id": world["work"]["location_id"],
            "material_id": world["material"]["id"],
            "quantity": "1",
        },
    )
    assert denied.status_code == 401
    too_much = client.post(
        "/api/consumptions",
        headers={**headers, "Idempotency-Key": "too-much"},
        json={
            "work_id": world["work"]["id"],
            "task_id": world["task"]["id"],
            "location_id": world["work"]["location_id"],
            "material_id": world["material"]["id"],
            "quantity": "31",
        },
    )
    assert too_much.status_code == 409
    foreign = client.post(
        "/api/consumptions",
        headers={**headers, "Idempotency-Key": "foreign"},
        json={
            "work_id": world["work"]["id"],
            "task_id": other["task"]["id"],
            "location_id": world["work"]["location_id"],
            "material_id": world["material"]["id"],
            "quantity": "1",
        },
    )
    assert foreign.status_code == 422
    assert "obra" in foreign.json()["detail"].lower()
    ok = client.post(
        "/api/consumptions",
        headers={**headers, "Idempotency-Key": "consume-5"},
        json={
            "work_id": world["work"]["id"],
            "task_id": world["task"]["id"],
            "location_id": world["work"]["location_id"],
            "material_id": world["material"]["id"],
            "quantity": "5",
        },
    )
    assert ok.status_code == 201, ok.text
    stock = client.get(
        "/api/stock/available",
        headers=headers,
        params={"material_id": world["material"]["id"], "location_id": world["work"]["location_id"]},
    ).json()
    assert stock["on_hand"] == "25.0000"


def test_consumption_correction_keeps_original(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-D")
    _receive(client, headers, world, "30")
    created = client.post(
        "/api/consumptions",
        headers={**headers, "Idempotency-Key": "cons-orig"},
        json=_consumption_body(world, "5"),
    ).json()
    correction = client.post(
        f"/api/consumptions/{created['id']}/corrections",
        headers={**headers, "Idempotency-Key": "cons-fix"},
        json={"quantity": "2", "reason": "Cantidad mal cargada"},
    )
    assert correction.status_code == 201, correction.text
    history = client.get("/api/consumptions", headers=headers, params={"work_id": world["work"]["id"]}).json()
    assert history["total"] == 2
    original = next(row for row in history["items"] if row["id"] == created["id"])
    assert original["status"] == "CONFIRMADO"
    assert original["quantity"] == "5.0000"
    stock = client.get(
        "/api/stock/available",
        headers=headers,
        params={"material_id": world["material"]["id"], "location_id": world["work"]["location_id"]},
    ).json()
    assert stock["on_hand"] == "27.0000"


def test_transfer_updates_balances_and_short_receipt_stays_unassigned(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-E")
    depot = client.post(
        "/api/locations",
        headers=headers,
        json={"name": "Galpón", "code": "GALPON-E", "location_type": "DEPOSITO"},
    ).json()
    _receive(client, headers, world, "30", location_id=depot["id"])
    transfer = client.post(
        "/api/transfers",
        headers=headers,
        json={
            "from_location_id": depot["id"],
            "to_location_id": world["work"]["location_id"],
            "authorized_by_user_id": client.get("/api/auth/me", headers=headers).json()["id"],
            "executed_operational_name": None,
            "items": [{"material_id": world["material"]["id"], "quantity": "10"}],
            "notes": "Envío a obra",
        },
    )
    assert transfer.status_code == 201, transfer.text
    transfer = transfer.json()
    assert transfer["status"] == "REGISTRADA"
    depot_stock = _stock(client, headers, world["material"]["id"], depot["id"])
    assert depot_stock == "30.0000"
    dispatched = client.post(
        f"/api/transfers/{transfer['id']}/dispatch",
        headers={**headers, "Idempotency-Key": "dispatch-1"},
        json={"executed_operational_name": "Juan Pérez"},
    )
    assert dispatched.status_code == 200, dispatched.text
    body = dispatched.json()
    assert body["status"] == "EN_TRANSITO"
    assert body["executed_operational_name"] == "Juan Pérez"
    assert body["created_by"]
    assert _stock(client, headers, world["material"]["id"], depot["id"]) == "20.0000"
    assert _stock(client, headers, world["material"]["id"], world["work"]["location_id"]) == "0.0000"
    received = client.post(
        f"/api/transfers/{transfer['id']}/receive",
        headers={**headers, "Idempotency-Key": "receive-1"},
        json={
            "items": [{"transfer_item_id": body["items"][0]["id"], "quantity": "7"}],
            "received_operational_name": "María López",
            "close_with_difference": True,
        },
    )
    assert received.status_code == 200, received.text
    closed = received.json()
    assert closed["status"] == "RECIBIDA_CON_DIFERENCIA"
    assert closed["received_operational_name"] == "María López"
    assert closed["items"][0]["qty_received"] == "7.0000"
    assert closed["items"][0]["in_transit"] == "0.0000"
    assert closed["items"][0]["discrepancies"][0]["status"] == "PENDIENTE"
    assert _stock(client, headers, world["material"]["id"], depot["id"]) == "20.0000"
    assert _stock(client, headers, world["material"]["id"], world["work"]["location_id"]) == "7.0000"


def test_cancel_in_transit_returns_stock(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-F")
    depot = client.post(
        "/api/locations",
        headers=headers,
        json={"name": "Galpón F", "code": "GALPON-F", "location_type": "DEPOSITO"},
    ).json()
    _receive(client, headers, world, "12", location_id=depot["id"])
    transfer = client.post(
        "/api/transfers",
        headers=headers,
        json={
            "from_location_id": depot["id"],
            "to_location_id": world["work"]["location_id"],
            "items": [{"material_id": world["material"]["id"], "quantity": "12"}],
        },
    ).json()
    client.post(
        f"/api/transfers/{transfer['id']}/dispatch",
        headers={**headers, "Idempotency-Key": "dispatch-cancel"},
        json={},
    )
    cancelled = client.post(
        f"/api/transfers/{transfer['id']}/cancel",
        headers=headers,
        json={"reason": "El camión no salió"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELADA"
    assert _stock(client, headers, world["material"]["id"], depot["id"]) == "12.0000"


def test_over_receipt_rejected_and_incompatible_unit_rejected(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-G")
    order = _order(client, headers, world, "10")
    confirmed = client.post(f"/api/purchase-orders/{order['id']}/confirm", headers=headers).json()
    extra = client.post(
        f"/api/purchase-orders/{order['id']}/receipts",
        headers={**headers, "Idempotency-Key": "over"},
        json={
            "location_id": world["work"]["location_id"],
            "items": [{"purchase_order_item_id": confirmed["items"][0]["id"], "quantity": "11"}],
        },
    )
    assert extra.status_code == 422
    rule = client.post(
        f"/api/tasks/{world['task']['id']}/rules",
        headers=headers,
        json={"material_id": world["material"]["id"], "coefficient": "6", "output_unit_id": world["m3"]},
    )
    assert rule.status_code == 422
    bad_reference = client.post(
        f"/api/tasks/{world['task']['id']}/rules",
        headers=headers,
        json={
            "material_id": world["material"]["id"],
            "coefficient": "6",
            "reference_unit_id": world["unit"],
        },
    )
    assert bad_reference.status_code == 422


def test_rule_change_does_not_rewrite_history_and_execution_does_not_double_count(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-H")
    rule = client.post(
        f"/api/tasks/{world['task']['id']}/rules",
        headers=headers,
        json={"material_id": world["material"]["id"], "coefficient": "6", "reason": "Ejemplo ilustrativo"},
    )
    assert rule.status_code == 201, rule.text
    rule = rule.json()
    first = client.post(
        f"/api/tasks/{world['task']['id']}/executions",
        headers={**headers, "Idempotency-Key": "exec-10"},
        json={"quantity_delta": "10"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["lines"][0]["output_qty"] == "60.0000"
    changed = client.post(
        f"/api/rules/{rule['id']}/versions",
        headers=headers,
        json={"coefficient": "8", "reason": "Cambio de criterio de esta tarea"},
    )
    assert changed.status_code == 201, changed.text
    same = client.post(
        f"/api/tasks/{world['task']['id']}/executions",
        headers={**headers, "Idempotency-Key": "exec-same"},
        json={"new_total": "10"},
    )
    assert same.status_code == 422
    second = client.post(
        f"/api/tasks/{world['task']['id']}/executions",
        headers={**headers, "Idempotency-Key": "exec-15"},
        json={"new_total": "15"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["quantity_delta"] == "5.0000"
    assert second.json()["lines"][0]["output_qty"] == "40.0000"
    theoretical = client.get(f"/api/tasks/{world['task']['id']}/theoretical", headers=headers).json()
    assert theoretical["executed_qty"] == "15.0000"
    assert theoretical["materials"][0]["theoretical_qty"] == "100.0000"
    history = client.get(f"/api/tasks/{world['task']['id']}/executions", headers=headers).json()
    assert history[0]["lines"][0]["output_qty"] == "60.0000"
    assert history[0]["lines"][0]["coefficient"] == "6.0000"


def test_retry_does_not_duplicate_consumption(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-I")
    _receive(client, headers, world, "20")
    body = _consumption_body(world, "4")
    first = client.post("/api/consumptions", headers={**headers, "Idempotency-Key": "same-key"}, json=body)
    second = client.post("/api/consumptions", headers={**headers, "Idempotency-Key": "same-key"}, json=body)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert _stock(client, headers, world["material"]["id"], world["work"]["location_id"]) == "16.0000"
    conflict = client.post(
        "/api/consumptions",
        headers={**headers, "Idempotency-Key": "same-key"},
        json=_consumption_body(world, "1"),
    )
    assert conflict.status_code == 409


def test_full_illustrative_comparison(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-J")
    client.post(
        f"/api/tasks/{world['task']['id']}/rules",
        headers=headers,
        json={"material_id": world["material"]["id"], "coefficient": "6"},
    )
    client.post(
        f"/api/tasks/{world['task']['id']}/executions",
        headers={**headers, "Idempotency-Key": "demo-exec"},
        json={"quantity_delta": "10"},
    )
    order = _order(client, headers, world, "100")
    client.post(f"/api/purchase-orders/{order['id']}/confirm", headers=headers)
    for key, qty in (("a", "60"), ("b", "40")):
        client.post(
            f"/api/purchase-orders/{order['id']}/receipts",
            headers={**headers, "Idempotency-Key": f"demo-{key}"},
            json={
                "location_id": world["work"]["location_id"],
                "items": [{"purchase_order_item_id": order["items"][0]["id"], "quantity": qty}],
            },
        )
    client.post(
        "/api/consumptions",
        headers={**headers, "Idempotency-Key": "demo-cons"},
        json=_consumption_body(world, "55"),
    )
    rows = client.get("/api/comparisons", headers=headers, params={"work_id": world["work"]["id"]}).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["theoretical_qty"] == "60.0000"
    assert row["real_qty"] == "55.0000"
    assert row["absolute_difference"] == "-5.0000"
    assert row["percent_deviation"] == "-8.33"
    assert row["stock_on_hand"] == "45.0000"
    detail = client.get(
        "/api/comparisons/detail",
        headers=headers,
        params={"task_id": world["task"]["id"], "material_id": world["material"]["id"]},
    ).json()
    assert len(detail["theoretical_lines"]) == 1
    assert len(detail["consumptions"]) == 1
    report = client.get("/api/reports/teorico-real", headers=headers, params={"work_id": world["work"]["id"], "format": "csv"})
    assert report.status_code == 200
    assert "60.0000" in report.text
    assert "55.0000" in report.text
    consistency = client.get("/api/stock/consistency", headers=headers)
    assert consistency.status_code == 200
    assert consistency.json()["ok"] is True


def test_concurrent_consumptions_cannot_exceed_stock(client):
    headers = auth(client)
    world = build_world(client, headers, "OBRA-K")
    _receive(client, headers, world, "10")
    me = client.get("/api/auth/me", headers=headers).json()
    from app.core.database import SessionLocal

    barrier = threading.Barrier(2)
    results = []

    def worker():
        db = SessionLocal()
        try:
            barrier.wait(timeout=5)
            user = db.get(User, me["id"])
            register_consumption(
                db,
                user,
                world["work"]["id"],
                world["task"]["id"],
                world["work"]["location_id"],
                world["material"]["id"],
                Decimal("10"),
                None,
                None,
            )
            db.commit()
            results.append(201)
        except AppError as exc:
            db.rollback()
            results.append(exc.status_code)
        finally:
            db.close()

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    second.start()
    first.join()
    second.join()
    assert sorted(results) == [201, 409]
    assert _stock(client, headers, world["material"]["id"], world["work"]["location_id"]) == "0.0000"


def _receive(client, headers, world, quantity, location_id=None):
    order = _order(client, headers, world, quantity)
    client.post(f"/api/purchase-orders/{order['id']}/confirm", headers=headers)
    response = client.post(
        f"/api/purchase-orders/{order['id']}/receipts",
        headers={**headers, "Idempotency-Key": f"recv-{world['work']['code']}-{quantity}-{location_id or 'obra'}"},
        json={
            "location_id": location_id or world["work"]["location_id"],
            "items": [{"purchase_order_item_id": order["items"][0]["id"], "quantity": quantity}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _order(client, headers, world, quantity):
    response = client.post(
        "/api/purchase-orders",
        headers=headers,
        json={
            "supplier_id": world["supplier"]["id"],
            "destination_location_id": world["work"]["location_id"],
            "work_id": world["work"]["id"],
            "items": [{"material_id": world["material"]["id"], "quantity": quantity}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _consumption_body(world, quantity):
    return {
        "work_id": world["work"]["id"],
        "task_id": world["task"]["id"],
        "location_id": world["work"]["location_id"],
        "material_id": world["material"]["id"],
        "quantity": quantity,
    }


def _stock(client, headers, material_id, location_id):
    return client.get(
        "/api/stock/available",
        headers=headers,
        params={"material_id": material_id, "location_id": location_id},
    ).json()["on_hand"]

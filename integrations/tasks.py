from podd_api.celery import app


@app.task
def record_report_submitted_event(report_id):
    from integrations.webhooks import record_report_submitted_event as record_event

    result = record_event(report_id=report_id)
    return {
        "event_id": str(result.event.event_id),
        "delivery_ids": [delivery.id for delivery in result.deliveries],
    }


@app.task
def attempt_webhook_delivery(delivery_id):
    from integrations.webhooks import attempt_webhook_delivery_by_id

    delivery = attempt_webhook_delivery_by_id(delivery_id)
    return {
        "delivery_id": delivery.id,
        "status": delivery.status,
        "attempt_count": delivery.attempt_count,
    }

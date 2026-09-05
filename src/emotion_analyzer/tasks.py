from celery import shared_task
from celery.utils.log import get_task_logger
from emotion_analyzer.services.poll_ha_data import poll_ha_data

logger = get_task_logger(__name__)

@shared_task
def analyze_emotions():
    """
    Background periodic task that polls Home Assistant credentials, cameras, 
    and entities, and performs emotion analysis.
    """
    logger.info("Starting Home Assistant emotion analysis polling background task")
    try:
        poll_cycle = poll_ha_data()
        if poll_cycle:
            logger.info(f"Successfully completed polling cycle ID: {poll_cycle.id}")
            return f"Success: Polling cycle ID {poll_cycle.id} created"
        else:
            logger.info("Polling task skipped (no Home Assistant credentials found)")
            return "Skipped: No Home Assistant credentials found"
    except Exception as e:
        logger.error(f"Error during periodic emotion analysis polling: {e}")
        raise e

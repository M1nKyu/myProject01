from ecoweb.app import create_app
from ecoweb.app.extensions import celery

# Flask app 초기화 (Celery worker에서 필요)
app = create_app()
app.app_context().push()

# Import tasks to register them with Celery
# This ensures all @shared_task decorated functions are registered
from ecoweb.app.tasks import analyze_url_task, generate_pdf_report_task

# Celery CLI가 모듈에서 'celery' 객체를 찾을 수 있도록 명시적으로 export
# celery는 이미 import되어 있으므로 모듈 레벨에서 접근 가능합니다
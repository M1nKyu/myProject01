import logging
from flask import request, session, has_request_context
import os

class RequestFormatter(logging.Formatter):
    """Custom formatter to include user email and request summary in all log messages"""
    
    def get_user_email(self):
        """Safely get user email from session"""
        try:
            # Check different possible session keys for user email
            if hasattr(session, 'get'):
                if 'user' in session and isinstance(session['user'], dict) and 'email' in session['user']:
                    return session['user']['email']
                return session.get('email', session.get('user_email', 'anonymous'))
        except Exception:
            pass
        return 'anonymous'
    
    def get_request_summary(self):
        """Get request method and path"""
        try:
            return f"{request.method} {request.path}"
        except Exception:
            return "<no-request>"
    
    def format(self, record):
        try:
            # Get user email and request info
            user_email = self.get_user_email()
            req_summary = self.get_request_summary() if has_request_context() else "<no-context>"
            
            # Add to log record
            if not hasattr(record, 'user_email'):
                record.user_email = user_email
            if not hasattr(record, 'request_info'):
                record.request_info = req_summary
                
            # Format the log message
            record.msg = f"[{user_email}] {req_summary} - {record.msg}"
            
        except Exception as e:
            # If anything fails, log the error but don't break the application
            record.msg = f"[logging-error] {str(e)} - {record.msg}"
        
        return super().format(record)

def configure_logging(app):
    """Configure logging for the Flask application"""
    
    # Set log level to WARNING to minimize verbose logs
    log_level = logging.WARNING
    
    # Common loggers to configure
    loggers = [
        None,  # root logger
        'werkzeug',
        'gunicorn',
        'gunicorn.access',
        'gunicorn.error',
        'urllib3',
        'requests',
        'sqlalchemy.engine',
        'asyncio',
        'app'  # Your application's logger
    ]
    
    # Create formatter
    formatter = RequestFormatter(
        '%(asctime)s [%(levelname)s] [%(user_email)s] %(request_info)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Configure each logger
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        
        # Clear existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Add our handler
        logger.addHandler(console_handler)
        
        # Set log level
        logger.setLevel(log_level)
        
        # Prevent propagation to avoid duplicate logs
        if logger_name is not None:  # Don't set propagate for root logger
            logger.propagate = False
    
    # Example of how to log a message with the new format:
    # app.logger.info("This is an info message")  # Will include [email] and request info
    # app.logger.error("An error occurred")       # Will include [email] and request info
    
    # Disable propagation for some loggers to prevent duplicate logs
    for logger_name in ['werkzeug']:
        logging.getLogger(logger_name).propagate = False
    
    # Set Flask app logger
    app.logger.setLevel(log_level)
    app.logger.handlers = []  # Remove default handlers
    app.logger.addHandler(console_handler)

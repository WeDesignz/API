import logging
from celery import shared_task
from django.core.management import call_command
from django.core.management.base import CommandError

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='MediaFiles.tasks.rename_design_files')
def rename_design_files_task(
    self,
    user_id=None,
    product_id=None,
    dry_run=False,
    verbose=False
):
    """
    Celery task to rename design files using product_number.
    
    This task wraps the rename_design_files management command to allow
    asynchronous execution via Celery.
    
    Args:
        user_id (int, optional): Process only files for a specific user ID
        product_id (int, optional): Process only files for a specific product ID
        dry_run (bool): Show what would be renamed without actually renaming files
        verbose (bool): Show detailed information for each file
    
    Returns:
        dict: Task result with status and message
    """
    logger.info(f"rename_design_files_task: starting user_id={user_id} product_id={product_id} dry_run={dry_run}")
    try:
        # Prepare command arguments
        command_args = []
        if user_id:
            command_args.extend(['--user-id', str(user_id)])
        if product_id:
            command_args.extend(['--product-id', str(product_id)])
        if dry_run:
            command_args.append('--dry-run')
        if verbose:
            command_args.append('--verbose')
        
        # Call the management command
        # Note: call_command doesn't return output, so we capture stdout
        from io import StringIO
        from django.core.management import call_command
        import sys
        
        # Redirect stdout to capture output
        old_stdout = sys.stdout
        sys.stdout = output = StringIO()
        
        try:
            call_command('rename_design_files', *command_args)
            output_text = output.getvalue()
            
            result = {
                'status': 'success',
                'message': 'Design files renamed successfully',
                'output': output_text
            }
            logger.info(f"rename_design_files_task: completed - {result['message']}")
            return result
        finally:
            sys.stdout = old_stdout
            
    except CommandError as e:
        raise self.retry(exc=e, countdown=60, max_retries=3)
    except Exception as e:
        raise self.retry(exc=e, countdown=60, max_retries=3)


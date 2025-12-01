from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils.text import slugify
from common.relations import attach_relation, get_related_ids, get_related, detach_relation
from MediaFiles.models import Media


class FeedbackQuestion(models.Model):
    TYPE_CHOICES = [
        ('rating', 'Rating'),
        ('review', 'Review'),
        ('yes_no', 'Yes/No'),
    ]
    
    STATUS_CHOICES = [
        ('enable', 'Enable'),
        ('disable', 'Disable'),
    ]
    
    FOR_CHOICES = [
        ('customers', 'Customers'),
        ('design_leads', 'Design Leads'),
        ('designers', 'Designers'),
    ]
    
    question = models.TextField()
    feedback_question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='enable')
    for_whom = models.CharField(max_length=20, choices=FOR_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_feedback_questions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_feedback_questions', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'feedback_question'
        verbose_name = 'Feedback Question'
        verbose_name_plural = 'Feedback Questions'
    
    def __str__(self):
        return f"Feedback Question {self.pk} - {self.question[:50]}..."


class FeedbackReview(models.Model):
    feedback_question = models.ForeignKey(FeedbackQuestion, on_delete=models.CASCADE, related_name='reviews')
    review = models.TextField()
    rating = models.IntegerField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_feedback_reviews')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        db_table = 'feedback_review'
        verbose_name = 'Feedback Review'
        verbose_name_plural = 'Feedback Reviews'
    
    def __str__(self):
        return f"Feedback Review {self.pk} - {self.created_by.username}"


class ReportIssue(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_issues')
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, default='medium', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ])
    status = models.CharField(max_length=20, default='open', choices=[
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ])
    resolution = models.TextField(blank=True, null=True)

    resolved_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resolved_issues', null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_report_issues')
    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_report_issues', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'report_issue'
        verbose_name = 'Report Issue'
        verbose_name_plural = 'Report Issues'
    
    def __str__(self):
        return f"Issue {self.pk} - {self.title}"
    
    def get_media(self):
        return get_related(self, 'ReportIssue:Media', Media)
    
    def attach_media(self, media_obj, meta=None, created_by=None):
        return attach_relation('ReportIssue:Media', self, media_obj, meta=meta, created_by=created_by)
    
    def detach_media(self, media_obj):
        return detach_relation('ReportIssue:Media', self, media_obj)


class SupportThread(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('technical', 'Technical'),
        ('billing', 'Billing'),
        ('account', 'Account'),
        ('order', 'Order'),
        ('other', 'Other'),
    ]
    
    THREAD_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('designer', 'Designer'),
    ]
    
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    thread_type = models.CharField(
        max_length=20, 
        choices=THREAD_TYPE_CHOICES, 
        default='customer',
        help_text='Type of thread: customer or designer'
    )
    
    # User who created the thread
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_support_threads')
    
    # Admin assigned to handle the thread
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        related_name='assigned_support_threads',
        null=True, 
        blank=True
    )
    
    # Resolution details
    resolution = models.TextField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        related_name='resolved_support_threads',
        null=True, 
        blank=True
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'support_thread'
        verbose_name = 'Support Thread'
        verbose_name_plural = 'Support Threads'
        ordering = ['-updated_at', '-created_at']
    
    def __str__(self):
        return f"Support Thread #{self.id} - {self.subject}"
    
    @property
    def last_activity(self):
        """Get the timestamp of the last message in this thread."""
        last_message = self.messages.order_by('-created_at').first()
        if last_message:
            return last_message.created_at
        return self.updated_at
    
    @property
    def message_count(self):
        """Get total number of messages in this thread."""
        return self.messages.count()
    
    def get_unread_count(self, user):
        """Get count of unread messages for a user."""
        # Count messages that:
        # 1. Are not sent by the current user
        # 2. Have not been read by the current user (read_by is not this user or read_by is null)
        unread_messages = self.messages.exclude(sender=user).filter(
            Q(read_by__isnull=True) | ~Q(read_by=user)
        )
        return unread_messages.count()


class SupportMessage(models.Model):
    thread = models.ForeignKey(
        SupportThread, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_support_messages')
    message = models.TextField()
    
    # Read tracking
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='read_support_messages',
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'support_message'
        verbose_name = 'Support Message'
        verbose_name_plural = 'Support Messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message #{self.id} in Thread #{self.thread.id}"
    
    def mark_as_read(self, user):
        """Mark message as read by a user."""
        from django.utils import timezone
        if not self.read_at or self.read_by != user:
            self.read_at = timezone.now()
            self.read_by = user
            self.save(update_fields=['read_at', 'read_by'])


class FAQ(models.Model):
    question = models.CharField(max_length=500)
    answer = models.TextField()
    slug = models.SlugField(blank=True, unique=True)
    is_active = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_faqs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_faqs', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'faq'
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["question"]),
            models.Index(fields=["is_active"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.question)[:50]
            self.slug = base
            # Ensure uniqueness
            counter = 1
            while FAQ.objects.filter(slug=self.slug).exists():
                self.slug = f"{base}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.question


class FAQTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    faqs = models.ManyToManyField(FAQ, related_name="tags")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_faq_tags')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_faq_tags', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'faq_tag'
        verbose_name = 'FAQ Tag'
        verbose_name_plural = 'FAQ Tags'
        ordering = ['name']

    def __str__(self):
        return self.name
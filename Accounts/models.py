from django.db import models
from django.contrib.auth.models import User
from common.relations import attach_relation, get_related_ids, get_related, detach_relation


class Role(models.Model):
    """
    Model to store user roles in the system.
    
    This model defines different roles that users can have in the system,
    such as admin, customer, designer, etc.
    """
    role = models.CharField(max_length=50, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_roles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_roles', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'role'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.role


class Permission(models.Model):
    """
    Model to store system permissions.
    
    This model defines specific permissions that can be assigned to roles,
    controlling what actions users can perform in the system.
    """
    permission = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_permissions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_permissions', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'permission'
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
    
    def __str__(self):
        return self.permission


class PermissionHasRole(models.Model):
    """
    Model to manage role-permission assignments.
    
    This model creates a many-to-many relationship between roles and permissions,
    allowing roles to have multiple permissions and permissions to be assigned to multiple roles.
    """
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permission_roles')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_permission_roles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_permission_roles', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'permission_has_role'
        verbose_name = 'Permission Has Role'
        verbose_name_plural = 'Permission Has Roles'
        unique_together = ['permission', 'role']
    
    def __str__(self):
        return f"{self.role.role} - {self.permission.permission}"
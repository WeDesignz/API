from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Role, Permission, PermissionHasRole


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for Django User model with basic user information.
    Used for nested serialization in other models.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer for Role model with full CRUD operations.
    Handles role creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Role
        fields = [
            'id', 'role', 'created_by', 'created_at', 
            'updated_by', 'updated_at', 'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_role(self, value):
        """
        Validate role uniqueness.
        """
        if Role.objects.filter(role=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Role already exists.")
        return value


class RoleListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Role model used in list views.
    """
    class Meta:
        model = Role
        fields = ['id', 'role', 'created_at']


class PermissionSerializer(serializers.ModelSerializer):
    """
    Serializer for Permission model with full CRUD operations.
    Handles permission creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Permission
        fields = [
            'id', 'permission', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_permission(self, value):
        """
        Validate permission uniqueness.
        """
        if Permission.objects.filter(permission=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Permission already exists.")
        return value


class PermissionListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Permission model used in list views.
    """
    class Meta:
        model = Permission
        fields = ['id', 'permission', 'created_at']


class PermissionHasRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for PermissionHasRole model with full CRUD operations.
    Handles role-permission assignments.
    """
    permission = PermissionSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    permission_id = serializers.IntegerField(write_only=True)
    role_id = serializers.IntegerField(write_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = PermissionHasRole
        fields = [
            'id', 'permission', 'role', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'permission_id', 'role_id',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """
        Validate that the permission-role combination is unique.
        """
        permission_id = attrs.get('permission_id')
        role_id = attrs.get('role_id')
        
        if PermissionHasRole.objects.filter(
            permission_id=permission_id, 
            role_id=role_id
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("This permission-role combination already exists.")
        
        return attrs


class PermissionHasRoleListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for PermissionHasRole model used in list views.
    """
    permission = PermissionListSerializer(read_only=True)
    role = RoleListSerializer(read_only=True)
    
    class Meta:
        model = PermissionHasRole
        fields = ['id', 'permission', 'role', 'created_at']


class BulkPermissionRoleSerializer(serializers.Serializer):
    """
    Serializer for bulk assignment of permissions to roles.
    """
    role_id = serializers.IntegerField()
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    
    def validate_role_id(self, value):
        """
        Validate that the role exists.
        """
        try:
            Role.objects.get(id=value)
        except Role.DoesNotExist:
            raise serializers.ValidationError("Role does not exist.")
        return value
    
    def validate_permission_ids(self, value):
        """
        Validate that all permissions exist.
        """
        existing_permissions = Permission.objects.filter(id__in=value).count()
        if existing_permissions != len(value):
            raise serializers.ValidationError("One or more permissions do not exist.")
        return value


class UserRolePermissionSerializer(serializers.Serializer):
    """
    Serializer for getting user's roles and permissions.
    """
    user_id = serializers.IntegerField()
    
    def validate_user_id(self, value):
        """
        Validate that the user exists.
        """
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist.")
        return value
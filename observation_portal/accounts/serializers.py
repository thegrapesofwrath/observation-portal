from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import ugettext as _

from observation_portal.accounts.models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    accept_terms = serializers.BooleanField(write_only=True, required=False)
    terms_accepted = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            'education_user', 'notifications_enabled', 'notifications_on_authored_only',
            'simple_interface', 'view_authored_requests_only', 'title', 'staff_view',
            'institution', 'api_quota', 'terms_accepted', 'accept_terms'
        )

    def validate_staff_view(self, staff_view):
        user = self.context.get('request').user
        is_not_staff = user and user.is_authenticated and not user.is_staff
        if staff_view and is_not_staff:
            raise serializers.ValidationError(_('Must be staff to set staff_view'))
        return staff_view

    def validate_accept_terms(self, accept_terms):
        if not accept_terms:
            raise serializers.ValidationError(_('accept_terms must be true'))
        return accept_terms


class UserSerializer(serializers.ModelSerializer):
    is_staff = serializers.BooleanField(read_only=True)
    proposals = serializers.SerializerMethodField()
    profile = ProfileSerializer(required=False)
    available_instrument_types = serializers.SerializerMethodField()
    tokens = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'username', 'first_name', 'last_name', 'email', 'profile', 'is_staff', 'proposals',
            'available_instrument_types', 'tokens'
        )

    def get_proposals(self, obj):
        return [
            {'id': proposal.id, 'title': proposal.title, 'current': proposal in obj.profile.current_proposals}
            for proposal in obj.proposal_set.all()
        ]

    def get_available_instrument_types(self, obj):
        instrument_types = set()
        for proposal in obj.proposal_set.filter(active=True):
            for timeallocation in proposal.timeallocation_set.all():
                if timeallocation.instrument_type:
                    instrument_types.add(timeallocation.instrument_type)
        return list(instrument_types)

    def get_tokens(self, obj):
        return {
            'archive': obj.profile.archive_bearer_token,
            'api_token': obj.profile.api_token.key
        }

    def validate_email(self, data):
        if data and User.objects.filter(email=data).exclude(pk=self.instance.id).exists():
            raise serializers.ValidationError(_('User with this email already exists'))
        return data

    def update(self, instance, validated_data):
        user_update_fields = ['email', 'username', 'last_name', 'first_name']
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.save(update_fields=user_update_fields)

        profile_data = validated_data.pop('profile', {})

        if 'accept_terms' in profile_data:
            profile_data['terms_accepted'] = timezone.now()
            del profile_data['accept_terms']

        if profile_data:
            Profile.objects.filter(pk=instance.profile.pk).update(**profile_data)

        return instance


class AccountRemovalSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)

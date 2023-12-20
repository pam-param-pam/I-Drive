from djoser.serializers import UserCreateSerializer as BaseUserRegistrationSerializer
from rest_framework import serializers

from website.models import Folder


class UserRegistrationSerializer(BaseUserRegistrationSerializer):
    def create(self, validated_data):
        print("creating a user")
        # TODO i dont remember what i wanted to do hear? create root folder ?
        # TODO well...




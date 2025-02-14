# coding: utf-8
#

from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.decorators import action
from django.utils.translation import ugettext_lazy as _
from django_filters import utils

from terminal import const
from common.const.http import GET
from terminal.filters import CommandStorageFilter, CommandFilter, CommandFilterForStorageTree
from ..models import CommandStorage, ReplayStorage
from ..serializers import CommandStorageSerializer, ReplayStorageSerializer

__all__ = [
    'CommandStorageViewSet', 'CommandStorageTestConnectiveApi',
    'ReplayStorageViewSet', 'ReplayStorageTestConnectiveApi'
]


class BaseStorageViewSetMixin:

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.type_null_or_server:
            data = {'msg': _('Deleting the default storage is not allowed')}
            return Response(data=data, status=status.HTTP_400_BAD_REQUEST)
        if instance.is_use():
            data = {'msg': _('Cannot delete storage that is being used')}
            return Response(data=data, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


class CommandStorageViewSet(BaseStorageViewSetMixin, viewsets.ModelViewSet):
    search_fields = ('name', 'type')
    queryset = CommandStorage.objects.all()
    serializer_class = CommandStorageSerializer
    filterset_class = CommandStorageFilter
    rbac_perms = {
        'tree': 'terminal.view_commandstorage | terminal.view_command'
    }

    @action(methods=[GET], detail=False, filterset_class=CommandFilterForStorageTree)
    def tree(self, request: Request):
        storage_qs = self.get_queryset().exclude(name='null')
        storages_with_count = []
        invalid_storages = []

        for storage in storage_qs:
            if not storage.is_valid():
                invalid_storages.append(storage)
                continue

            command_qs = storage.get_command_queryset()
            filterset = CommandFilter(
                data=request.query_params, queryset=command_qs,
                request=request
            )
            if not filterset.is_valid():
                raise utils.translate_validation(filterset.errors)
            command_qs = filterset.qs
            if storage.type == const.CommandStorageTypeChoices.es:
                command_count = command_qs.count(limit_to_max_result_window=False)
            else:
                command_count = command_qs.count()
            storages_with_count.append((storage, command_count))

        root = {
            'id': 'root',
            'name': _('Command storages'),
            'title': _('Command storages'),
            'pId': '',
            'isParent': True,
            'open': True,
        }

        invalid = _('Invalid')
        nodes = [
            {
                'id': storage.id,
                'name': f'{storage.name}({storage.type})({command_count})',
                'title': f'{storage.name}({storage.type})',
                'pId': 'root',
                'isParent': False,
                'open': False,
                'valid': True,
            } for storage, command_count in storages_with_count
        ] + [
            {
                'id': storage.id,
                'name': f'{storage.name}({storage.type}) *{invalid}',
                'title': f'{storage.name}({storage.type})',
                'pId': 'root',
                'isParent': False,
                'open': False,
                'valid': False,
            } for storage in invalid_storages
        ]
        nodes.append(root)
        return Response(data=nodes)


class ReplayStorageViewSet(BaseStorageViewSetMixin, viewsets.ModelViewSet):
    filterset_fields = ('name', 'type', 'is_default')
    search_fields = filterset_fields
    queryset = ReplayStorage.objects.all()
    serializer_class = ReplayStorageSerializer


class BaseStorageTestConnectiveMixin:
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            is_valid = instance.is_valid()
        except Exception as e:
            is_valid = False
            msg = _("Test failure: {}".format(str(e)))
        else:
            if is_valid:
                msg = _("Test successful")
            else:
                msg = _("Test failure: Account invalid")
        data = {
            'is_valid': is_valid,
            'msg': msg
        }
        return Response(data)


class CommandStorageTestConnectiveApi(BaseStorageTestConnectiveMixin, generics.RetrieveAPIView):
    queryset = CommandStorage.objects.all()


class ReplayStorageTestConnectiveApi(BaseStorageTestConnectiveMixin, generics.RetrieveAPIView):
    queryset = ReplayStorage.objects.all()

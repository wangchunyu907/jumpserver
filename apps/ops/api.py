# ~*~ coding: utf-8 ~*~
import uuid
import re

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, generics
from rest_framework.generics import RetrieveAPIView
from rest_framework.views import Response

from .hands import IsSuperUser
from .models import Task, AdHoc, AdHocRunHistory
from .serializers import TaskSerializer, AdHocSerializer, AdHocRunHistorySerializer
from .tasks import run_ansible_task


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = (IsSuperUser,)


class TaskRun(generics.RetrieveAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskViewSet
    permission_classes = (IsSuperUser,)

    def retrieve(self, request, *args, **kwargs):
        task = self.get_object()
        run_ansible_task.delay(str(task.id))
        return Response({"msg": "start"})


class AdHocViewSet(viewsets.ModelViewSet):
    queryset = AdHoc.objects.all()
    serializer_class = AdHocSerializer
    permission_classes = (IsSuperUser,)

    def get_queryset(self):
        task_id = self.request.query_params.get('task')
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            self.queryset = self.queryset.filter(task=task)
        return self.queryset


class AdHocRunHistorySet(viewsets.ModelViewSet):
    queryset = AdHocRunHistory.objects.all()
    serializer_class = AdHocRunHistorySerializer
    permission_classes = (IsSuperUser,)

    def get_queryset(self):
        task_id = self.request.query_params.get('task')
        adhoc_id = self.request.query_params.get('adhoc')
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            adhocs = task.adhoc.all()
            self.queryset = self.queryset.filter(adhoc__in=adhocs)

        if adhoc_id:
            adhoc = get_object_or_404(AdHoc, id=adhoc_id)
            self.queryset = self.queryset.filter(adhoc=adhoc)
        return self.queryset


class AdHocHistoryOutputAPI(RetrieveAPIView):
    queryset = AdHocRunHistory.objects.all()
    permission_classes = (IsSuperUser,)
    buff_size = 1024 * 10
    end = False

    def retrieve(self, request, *args, **kwargs):
        history = self.get_object()
        mark = request.query_params.get("mark") or str(uuid.uuid4())

        with open(history.log_path, 'r') as f:
            offset = cache.get(mark, 0)
            f.seek(offset)
            data = f.read(self.buff_size).replace('\n', '\r\n')
            print(repr(data))
            mark = str(uuid.uuid4())
            cache.set(mark, f.tell(), 5)

            if history.is_finished and data == '':
                self.end = True
            return Response({"data": data, 'end': self.end, 'mark': mark})

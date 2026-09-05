from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django import forms
from .models import HomeAssistantCredentials, Entity, Camera, PollCycle
from django_celery_beat.models import PeriodicTask, IntervalSchedule

class HomeAssistantCredentialsForm(forms.ModelForm):
    token = forms.CharField(widget=forms.PasswordInput(render_value=False), required=False, label="Access Token")

    class Meta:
        model = HomeAssistantCredentials
        fields = ['username', 'host', 'port']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            self.fields['token'].required = True

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and HomeAssistantCredentials.objects.exists():
            raise forms.ValidationError("Only one Home Assistant Credentials object is allowed. Please edit or delete the existing configuration.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        token = self.cleaned_data.get('token')
        if token:
            instance.token = token
        if commit:
            instance.save()
        return instance

class EntityForm(forms.ModelForm):
    class Meta:
        model = Entity
        fields = ['entity_id', 'name', 'location', 'unit_of_measurement']

class CameraForm(forms.ModelForm):
    class Meta:
        model = Camera
        fields = ['camera_id', 'name', 'location']


@login_required
def configuration_page_view(request):
    active_tab = request.GET.get('tab', 'credentials')
    
    # Load all models
    credentials = HomeAssistantCredentials.objects.all()
    entities = Entity.objects.all()
    cameras = Camera.objects.all()
    
    # Edit IDs from query parameters
    edit_credential_id = request.GET.get('edit_credential')
    edit_entity_id = request.GET.get('edit_entity')
    edit_camera_id = request.GET.get('edit_camera')
    
    # Initialize forms
    credential_form = None
    entity_form = None
    camera_form = None
    
    # Load instances for edit mode
    if edit_credential_id:
        try:
            instance = HomeAssistantCredentials.objects.get(pk=edit_credential_id)
            credential_form = HomeAssistantCredentialsForm(instance=instance)
        except HomeAssistantCredentials.DoesNotExist:
            pass
    if edit_entity_id:
        try:
            instance = Entity.objects.get(pk=edit_entity_id)
            entity_form = EntityForm(instance=instance)
        except Entity.DoesNotExist:
            pass
    if edit_camera_id:
        try:
            instance = Camera.objects.get(pk=edit_camera_id)
            camera_form = CameraForm(instance=instance)
        except Camera.DoesNotExist:
            pass
            
    # Handle forms submission (Add/Edit/Delete)
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_credential':
            credential_form = HomeAssistantCredentialsForm(request.POST)
            if credential_form.is_valid():
                cred = credential_form.save(commit=False)
                cred.user = request.user
                cred.save()
                return redirect('/?tab=credentials')
            active_tab = 'credentials'
            
        elif action == 'edit_credential':
            try:
                pk = request.POST.get('pk')
                instance = HomeAssistantCredentials.objects.get(pk=pk)
                credential_form = HomeAssistantCredentialsForm(request.POST, instance=instance)
                if credential_form.is_valid():
                    cred = credential_form.save(commit=False)
                    cred.user = request.user
                    cred.save()
                    return redirect('/?tab=credentials')
            except HomeAssistantCredentials.DoesNotExist:
                pass
            active_tab = 'credentials'
            
        elif action == 'delete_credential':
            try:
                pk = request.POST.get('pk')
                HomeAssistantCredentials.objects.filter(pk=pk).delete()
            except Exception:
                pass
            return redirect('/?tab=credentials')
            
        elif action == 'add_entity':
            entity_form = EntityForm(request.POST)
            if entity_form.is_valid():
                entity_form.save()
                return redirect('/?tab=entities')
            active_tab = 'entities'
            
        elif action == 'edit_entity':
            try:
                pk = request.POST.get('pk')
                instance = Entity.objects.get(pk=pk)
                entity_form = EntityForm(request.POST, instance=instance)
                if entity_form.is_valid():
                    entity_form.save()
                    return redirect('/?tab=entities')
            except Entity.DoesNotExist:
                pass
            active_tab = 'entities'
            
        elif action == 'delete_entity':
            try:
                pk = request.POST.get('pk')
                Entity.objects.filter(pk=pk).delete()
            except Exception:
                pass
            return redirect('/?tab=entities')
            
        elif action == 'add_camera':
            camera_form = CameraForm(request.POST)
            if camera_form.is_valid():
                camera_form.save()
                return redirect('/?tab=cameras')
            active_tab = 'cameras'
            
        elif action == 'edit_camera':
            try:
                pk = request.POST.get('pk')
                instance = Camera.objects.get(pk=pk)
                camera_form = CameraForm(request.POST, instance=instance)
                if camera_form.is_valid():
                    camera_form.save()
                    return redirect('/?tab=cameras')
            except Camera.DoesNotExist:
                pass
            active_tab = 'cameras'
            
        elif action == 'delete_camera':
            try:
                pk = request.POST.get('pk')
                Camera.objects.filter(pk=pk).delete()
            except Exception:
                pass
            return redirect('/?tab=cameras')
            
    # Default initialize forms if not set (for empty insert forms)
    if credential_form is None:
        credential_form = HomeAssistantCredentialsForm()
    if entity_form is None:
        entity_form = EntityForm()
    if camera_form is None:
        camera_form = CameraForm()
        
    context = {
        'credentials': credentials,
        'entities': entities,
        'cameras': cameras,
        'credential_form': credential_form,
        'entity_form': entity_form,
        'camera_form': camera_form,
        'active_tab': active_tab,
        'edit_credential_id': int(edit_credential_id) if edit_credential_id and edit_credential_id.isdigit() else None,
        'edit_entity_id': int(edit_entity_id) if edit_entity_id and edit_entity_id.isdigit() else None,
        'edit_camera_id': int(edit_camera_id) if edit_camera_id and edit_camera_id.isdigit() else None,
    }
    return render(request, 'emotion_analyzer/configuration.html', context)

@login_required
def run_page_view(request):
    task_name = 'Analyze Emotions Periodic Task'
    test_result = None
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'start':
            every_val = request.POST.get('every', 30)
            period_val = request.POST.get('period', 'seconds')
            try:
                every_val = int(every_val)
                if every_val <= 0:
                    every_val = 30
            except ValueError:
                every_val = 30
            if period_val not in ['seconds', 'minutes', 'hours', 'days']:
                period_val = 'seconds'
                
            schedule, created = IntervalSchedule.objects.get_or_create(
                every=every_val,
                period=period_val,
            )
            PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    'interval': schedule,
                    'task': 'emotion_analyzer.tasks.analyze_emotions',
                    'enabled': True,
                }
            )
            return redirect('run_page')
            
        elif action == 'stop':
            try:
                task = PeriodicTask.objects.get(name=task_name)
                task.enabled = False
                task.save()
            except PeriodicTask.DoesNotExist:
                pass
            return redirect('run_page')
            
        elif action == 'test':
            from emotion_analyzer.services.test_ha_connection import test_ha_connection
            result_message = test_ha_connection()
            
            credentials_status = "OK"
            api_status = "OK"
            entities_status = "OK"
            model_status = "OK"
            overall_success = True
            
            if result_message:
                overall_success = False
                msg_lower = result_message.lower()
                if "credentials" in msg_lower or "database for credentials" in msg_lower:
                    credentials_status = "FAILED"
                    api_status = "NOT RUN"
                    entities_status = "NOT RUN"
                    model_status = "NOT RUN"
                elif "connect to home assistant api" in msg_lower:
                    api_status = "FAILED"
                    entities_status = "NOT RUN"
                    model_status = "NOT RUN"
                elif "entity" in msg_lower:
                    entities_status = "FAILED"
                    model_status = "NOT RUN"
                else:
                    model_status = "FAILED"
            
            test_result = {
                'overall_success': overall_success,
                'error_message': result_message,
                'steps': [
                    {'name': 'Home Assistant Credentials', 'status': credentials_status},
                    {'name': 'Home Assistant API Connection', 'status': api_status},
                    {'name': 'Entity Data Polling', 'status': entities_status},
                    {'name': 'Emotion Recognition Model', 'status': model_status},
                ]
            }

    try:
        task = PeriodicTask.objects.get(name=task_name)
        is_running = task.enabled
        interval_every = task.interval.every
        interval_period = task.interval.period
    except PeriodicTask.DoesNotExist:
        is_running = False
        interval_every = 30
        interval_period = 'seconds'
        
    return render(request, 'emotion_analyzer/run.html', {
        'is_running': is_running,
        'test_result': test_result,
        'interval_every': interval_every,
        'interval_period': interval_period,
    })

@login_required
def results_page_view(request):
    import csv
    from django.http import HttpResponse

    cameras = list(Camera.objects.all().order_by('id'))
    entities = list(Entity.objects.all().order_by('id'))

    poll_cycles = PollCycle.objects.all().prefetch_related('snapshots', 'statuses').order_by('-timestamp')

    if request.GET.get('download') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="emotion_analysis_results.csv"'
        
        writer = csv.writer(response)
        
        headers = ['Timestamp']
        for camera in cameras:
            prefix = camera.name or camera.camera_id
            headers.extend([
                f"{prefix}_camera_id",
                f"{prefix}_name",
                f"{prefix}_location",
                f"{prefix}_image",
                f"{prefix}_detected_emotion",
                f"{prefix}_confidence_score"
            ])
        for entity in entities:
            prefix = entity.name or entity.entity_id
            headers.extend([
                f"{prefix}_entity_id",
                f"{prefix}_name",
                f"{prefix}_location",
                f"{prefix}_unit_of_measurement",
                f"{prefix}_state_value"
            ])
        writer.writerow(headers)

        for cycle in poll_cycles:
            row = [cycle.timestamp.strftime('%Y-%m-%d %H:%M:%S')]
            
            snapshots_map = {snap.camera_id: snap for snap in cycle.snapshots.all()}
            statuses_map = {status.entity_id: status for status in cycle.statuses.all()}
            
            for camera in cameras:
                snap = snapshots_map.get(camera.id)
                row.extend([
                    camera.camera_id,
                    camera.name,
                    camera.location,
                    snap.image.name if (snap and snap.image) else '',
                    snap.detected_emotion if snap else '',
                    snap.confidence_score if snap else ''
                ])
                
            for entity in entities:
                status = statuses_map.get(entity.id)
                row.extend([
                    entity.entity_id,
                    entity.name,
                    entity.location,
                    entity.unit_of_measurement or '',
                    status.state_value if status else ''
                ])
                
            writer.writerow(row)
        return response

    from django.core.paginator import Paginator

    paginator = Paginator(poll_cycles, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    rows = []
    for cycle in page_obj:
        snapshots_map = {snap.camera_id: snap for snap in cycle.snapshots.all()}
        statuses_map = {status.entity_id: status for status in cycle.statuses.all()}

        camera_data = []
        for camera in cameras:
            snap = snapshots_map.get(camera.id)
            camera_data.append({
                'detected_emotion': snap.detected_emotion if snap else None,
                'confidence_score': snap.confidence_score if snap else None,
            })

        entity_data = []
        for entity in entities:
            status = statuses_map.get(entity.id)
            entity_data.append({
                'state_value': status.state_value if status else None,
                'unit_of_measurement': entity.unit_of_measurement,
            })

        rows.append({
            'timestamp': cycle.timestamp,
            'camera_data': camera_data,
            'entity_data': entity_data,
        })

    total_columns = 1 + (len(cameras) * 2) + (len(entities) * 2)

    context = {
        'cameras': cameras,
        'entities': entities,
        'rows': rows,
        'total_columns': total_columns,
        'page_obj': page_obj,
    }
    return render(request, 'emotion_analyzer/results.html', context)


from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    return redirect('configuration_page')
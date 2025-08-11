from django.shortcuts import render
from django.views.generic.list import ListView
from fire.models import Locations, Incident, FireStation, Firefighters, FireTruck, WeatherConditions
from django.db import connection
from django.http import JsonResponse
from django.db.models.functions import ExtractMonth
from django.contrib import messages
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from fire.forms import LocationForm, IncidentForm, FireStationForm, FirefightersForm, FireTruckForm, WeatherConditionsForm
from typing import Any
from django.db.models.query import QuerySet
from django.db.models import Q

from django.db.models import Count
from datetime import datetime


class HomePageView(ListView):
    model = Locations
    context_object_name = 'home'
    template_name = "home.html"

class ChartView(ListView):
    template_name = 'chart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_queryset(self, *args, **kwargs):
        pass

def PieCountbySeverity(request):
    query = '''
    SELECT severity_level, COUNT(*) as count 
    FROM fire_incident
    GROUP BY severity_level
    '''
    data = {}
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
        if rows:
            # Construct the dictionary with severity level as keys and count as values 
            data = {severity: count for severity, count in rows}
        else:
            data = {}

    return JsonResponse(data)

def LineCountByMonth(request):
    current_year = datetime.now().year
    result = {month: 0 for month in range(1, 13)}

    incidents_per_month = Incident.objects.filter(date_time__year=current_year).values_list('date_time', flat=True)

    # Counting the number of incidents per month
    for date_time in incidents_per_month:
        month = date_time.month
        result[month] += 1

    # Mapping month numbers to month names
    month_names = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }

    result_with_month_names = {month_names[month]: count for month, count in result.items()}

    return JsonResponse(result_with_month_names)

def MultilineIncidentTop3Country(request):
    query = '''
        SELECT 
        fl.country, 
        strftime('%m', fi.date_time) AS month, 
        COUNT(fi.id) AS incident_count
    FROM 
        fire_incident fi
    JOIN 
        fire_locations fl ON fi.location_id = fl.id
    WHERE 
        fl.country IN (
            SELECT 
                fl_top.country
            FROM 
                fire_incident fi_top
            JOIN 
                fire_locations fl_top ON fi_top.location_id = fl_top.id
            WHERE 
                strftime('%Y', fi_top.date_time) = strftime('%Y', 'now')
            GROUP BY 
                fl_top.country
            ORDER BY 
                COUNT(fi_top.id) DESC
            LIMIT 3
        )
        AND strftime('%Y', fi.date_time) = strftime('%Y', 'now')
    GROUP BY 
        fl.country, month
    ORDER BY 
        fl.country, month;
    '''

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    # Initialize a dictionary to store the result
    result = {}
    
    # Initalize a set of months from January to December
    months = set(str(i).zfill(2) for i in range(1, 13))

    # Loop through the query results
    for row in rows:
        country = row[0]
        month = row[1]
        total_incidents = row[2]

        # If the country is not in the result dictionary, initialize it with all months set to zero
        if country not in result:
            result[country] = {month: 0 for month in months}
        
        # Update the incident count for the corresponding month
        result[country][month] = total_incidents

    # Ensure there are always 3 countries in the result
    while len(result) < 3:
        # Placeholder name for missing countries
        missing_country = f"Country {len(result) + 1}"
        result[missing_country] = {month: 0 for month in months}

    for country in result:
        result[country] = dict(sorted(result[country].items()))

    return JsonResponse(result)

def multipleBarbySeverity(request):
    query = '''
        SELECT
            fi.severity_level,
            strftime('%m', fi.date_time) AS month, 
            COUNT(fi.id) AS incident_count
        FROM 
            fire_incident fi
        GROUP BY fi.severity_level, month
        '''

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    result = {}
    months = set(str(i).zfill(2) for i in range(1, 13))

    # Loop through the query results
    for row in rows:
        level = str(row[0])  # Ensure the severity level is a string
        month = row[1]
        total_incidents = row[2]

        if level not in result:
            result[level] = {month: 0 for month in months}
        
        result[level][month] = total_incidents

    # Sort months within each severity level
    for level in result:
        result[level] = dict(sorted(result[level].items()))

    return JsonResponse(result)


def map_station(request):
    stations = FireStation.objects.all()
    fireStations_list = [{
        'name': station.name,
        'latitude': float(station.latitude),
        'longitude': float(station.longitude),
    } for station in stations]

    context = {
        'fireStations': fireStations_list,
        'stations': stations,
    }
    return render(request, 'map_station.html', context)

def map_incidents(request):
    incidents = Incident.objects.select_related('location').all()
    fireIncidents = [{
         'id': incident.id,
         'latitude': float(incident.location.latitude),
         'longitude': float(incident.location.longitude),
         'description': incident.description
    } for incident in incidents]
    severity_levels = ["Minor Fire", "Moderate Fire", "Major Fire"]
    context = {
        'fireIncidents': fireIncidents,
        'severity_levels': severity_levels,
    }
    return render(request, 'incidents_map.html', context)

class LocationList(ListView):
    model = Locations
    context_object_name = 'object_list'
    template_name = 'location_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super(LocationList, self).get_queryset(*args, **kwargs)
        if self.request.GET.get('q') != None:
            query = self.request.GET.get('q')
            qs = qs.filter(Q(name__icontains=query) | Q(address__icontains=query) | Q(city__icontains=query) | Q(country__icontains=query))
        return qs

class LocationCreateView(CreateView):
    model = Locations
    form_class = LocationForm
    template_name = 'location_add.html'
    success_url = reverse_lazy('location-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Location '{self.object.name}' was added successfully.")
        return response

class LocationUpdateView(UpdateView):
    model = Locations
    form_class = LocationForm
    template_name = 'location_edit.html'
    success_url = reverse_lazy('location-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Location '{self.object.name}' was updated successfully.")
        return response

class LocationDeleteView(DeleteView):
    model = Locations
    template_name = 'location_del.html'
    success_url = reverse_lazy('location-list')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Location '{obj.name}' was deleted successfully.")
        return super().delete(request, *args, **kwargs)

class IncidentList(ListView):
    model = Incident
    context_object_name = 'object_list'
    template_name = 'incidents_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get('q'):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(description__icontains=query) | Q(severity_level__icontains=query))
        return qs

class IncidentCreateView(CreateView):
    model = Incident
    form_class = IncidentForm
    template_name = 'incidents_add.html'
    success_url = reverse_lazy('incident-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Incident '{self.object}' was added successfully.")
        return response

class IncidentUpdateView(UpdateView):
    model = Incident
    form_class = IncidentForm
    template_name = 'incidents_edit.html'
    success_url = reverse_lazy('incident-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Incident '{self.object}' was updated successfully.")
        return response

class IncidentDeleteView(DeleteView):
    model = Incident
    template_name = 'incidents_del.html'
    success_url = reverse_lazy('incident-list')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Incident '{obj}' was deleted successfully.")
        return super().delete(request, *args, **kwargs)

class FireStationList(ListView):
    model = FireStation
    context_object_name = 'object_list'
    template_name = 'firestations_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get('q'):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(name__icontains=query) | Q(address__icontains=query) | Q(city__icontains=query) | Q(country__icontains=query))
        return qs

class FireStationCreateView(CreateView):
    model = FireStation
    form_class = FireStationForm
    template_name = 'firestations_add.html'
    success_url = reverse_lazy('firestations-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Fire Station '{self.object.name}' was added successfully.")
        return response

class FireStationUpdateView(UpdateView):
    model = FireStation
    form_class = FireStationForm
    template_name = 'firestations_edit.html'
    success_url = reverse_lazy('firestations-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Fire Station '{self.object.name}' was updated successfully.")
        return response

class FireStationDeleteView(DeleteView):
    model = FireStation
    template_name = 'firestations_del.html'
    success_url = reverse_lazy('firestations-list')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Fire Station '{obj.name}' was deleted successfully.")
        return super().delete(request, *args, **kwargs)

class FirefightersList(ListView):
    model = Firefighters
    context_object_name = 'object_list'
    template_name = 'firefighters_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get('q'):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(name__icontains=query) | Q(rank__icontains=query) | Q(experience_level__icontains=query) | Q(station__icontains=query))
        return qs

class FirefightersCreateView(CreateView):
    model = Firefighters
    form_class = FirefightersForm
    template_name = 'firefighters_add.html'
    success_url = reverse_lazy('firefighters-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Fire Fighter '{self.object.name}' was added successfully.")
        return response

class FirefightersUpdateView(UpdateView):
    model = Firefighters
    form_class = FirefightersForm
    template_name = 'firefighters_edit.html'
    success_url = reverse_lazy('firefighters-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Fire Fighter '{self.object.name}' was updated successfully.")
        return response

class FirefightersDeleteView(DeleteView):
    model = Firefighters
    template_name = 'firefighters_del.html'
    success_url = reverse_lazy('firefighters-list')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Fire Fighter '{obj.name}' was deleted successfully.")
        return super().delete(request, *args, **kwargs)

class FireTruckList(ListView):
    model = FireTruck
    context_object_name = 'object_list'
    template_name = 'firetrucks_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get('q'):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(truck_number__icontains=query) | Q(model__icontains=query) | Q(capacity__icontains=query) | Q(station__name__icontains=query))
        return qs

class FireTruckCreateView(CreateView):
    model = FireTruck
    form_class = FireTruckForm
    template_name = 'firetrucks_add.html'
    success_url = reverse_lazy('firetrucks-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Fire Truck '{self.object.truck_number}' was added successfully.")
        return response

class FireTruckUpdateView(UpdateView):
    model = FireTruck
    form_class = FireTruckForm
    template_name = 'firetrucks_edit.html'
    success_url = reverse_lazy('firetrucks-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Fire Truck '{self.object.truck_number}' was updated successfully.")
        return response

class FireTruckDeleteView(DeleteView):
    model = FireTruck
    template_name = 'firetrucks_del.html'
    success_url = reverse_lazy('firetrucks-list')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Fire Truck '{obj.truck_number}' was deleted successfully.")
        return super().delete(request, *args, **kwargs)

class WeatherConditionsList(ListView):
    model = WeatherConditions
    context_object_name = 'object_list'
    template_name = 'weathercon_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get('q'):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(incident__description__icontains=query) | Q(weather_description__icontains=query) | Q(temperature__icontains=query) | Q(humidity__icontains=query) | Q(wind_speed__icontains=query))
        return qs

class WeatherConditionsCreateView(CreateView):
    model = WeatherConditions
    form_class = WeatherConditionsForm
    template_name = 'weathercon_add.html'
    success_url = reverse_lazy('weathercon-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Weather Condition '{self.object}' was added successfully.")
        return response

class WeatherConditionsUpdateView(UpdateView):
    model = WeatherConditions
    form_class = WeatherConditionsForm
    template_name = 'weathercon_edit.html'
    success_url = reverse_lazy('weathercon-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Weather Condition '{self.object}' was updated successfully.")
        return response

class WeatherConditionsDeleteView(DeleteView):
    model = WeatherConditions
    template_name = 'weathercon_del.html'
    success_url = reverse_lazy('weathercon-list')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Weather Condition '{obj}' was deleted successfully.")
        return super().delete(request, *args, **kwargs)
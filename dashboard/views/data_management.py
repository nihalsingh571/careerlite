import json
import math
import re

from contextlib import contextmanager
from urllib.parse import quote

from django.urls import reverse
from django.db.models import Count, Q
from django.http.response import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.defaultfilters import slugify
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models.signals import post_delete, post_save

from mpcomp.views import (
    get_aws_file_path,
    get_prev_after_pages_count,
    permission_required,
)
from mpcomp.aws import AWS
from peeldb.models import (
    City,
    Country,
    FunctionalArea,
    Industry,
    JobPost,
    Language,
    Qualification,
    Skill,
    State,
    SKILL_TYPE,
    User,
)
from ..forms import (
    CityForm,
    CountryForm,
    FunctionalAreaForm,
    IndustryForm,
    LanguageForm,
    QualificationForm,
    SkillForm,
    StateForm,
)


# Functions to move here from main views.py:


@contextmanager
def disable_haystack_signals():
    disconnected = []
    for signal in (post_save, post_delete):
        for receiver in list(signal.receivers):
            receiver_ref = receiver[1]
            resolved = None
            if hasattr(receiver_ref, "__call__"):
                try:
                    resolved = receiver_ref()
                except TypeError:
                    resolved = receiver_ref
            if resolved and getattr(resolved, "__module__", "").startswith("haystack"):
                signal.disconnect(resolved)
                disconnected.append((signal, resolved))
    try:
        yield
    finally:
        for signal, receiver in disconnected:
            try:
                signal.connect(receiver)
            except Exception:
                pass


DEVICON_ALIASES = {
    "c#": "csharp",
    "c-sharp": "csharp",
    "csharp": "csharp",
    "c++": "cplusplus",
    "c-plus-plus": "cplusplus",
    "cplusplus": "cplusplus",
    ".net": "dotnet",
    "dot net": "dotnet",
    "dotnet": "dotnet",
    "asp.net": "dotnet",
    "html5": "html5",
    "css3": "css3",
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "nodejs": "nodejs",
    "node.js": "nodejs",
    "javascript": "javascript",
    "typescript": "typescript",
    "python": "python",
    "django": "django",
    "flask": "flask",
    "java": "java",
    "spring": "spring",
    "springboot": "spring",
    "angular": "angular",
    "vue": "vuejs",
    "vuejs": "vuejs",
    "mysql": "mysql",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mongodb": "mongodb",
    "aws": "amazonwebservices",
    "azure": "azure",
    "gcp": "googlecloud",
    "google cloud": "googlecloud",
    "php": "php",
    "laravel": "laravel",
    "swift": "swift",
    "kotlin": "kotlin",
    "android": "android",
    "ios": "ios",
}


def fallback_skill_icon(name):
    seed = quote(name or "Skill")
    return (
        "https://api.dicebear.com/6.x/initials/svg"
        f"?seed={seed}&backgroundType=gradientLinear"
    )


def normalise_devicon_slug(name, slug):
    base = (slug or name or "").strip().lower()
    if not base:
        return None
    base = DEVICON_ALIASES.get(base, base)
    base = (
        base.replace("c#", "csharp")
        .replace("c++", "cplusplus")
        .replace("+", "plus")
        .replace("#", "sharp")
        .replace(".", "")
    )
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or None


def devicon_icon(name, slug):
    normalised = normalise_devicon_slug(name, slug)
    if not normalised:
        return None
    return (
        "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/"
        f"{normalised}/{normalised}-original.svg"
    )


def resolve_skill_icon(skill):
    icon = getattr(skill, "icon", None)
    if icon:
        icon = icon.strip()
        lower_icon = icon.lower()
        if icon.startswith(("http://", "https://")):
            return {"type": "url", "primary": icon, "fallback": icon}
        if "/" in icon or "." in icon:
            url = icon
            if not icon.startswith(("http://", "https://")):
                url = f"https://cdn.careerlite.com/{icon.lstrip('/')}"
            return {"type": "url", "primary": url, "fallback": url}
        if lower_icon.startswith('fa') or lower_icon.startswith('icon-') or ' fa-' in lower_icon:
            return {"type": "class", "primary": icon, "fallback": fallback_skill_icon(skill.name)}

    devicon_url = devicon_icon(skill.name, getattr(skill, "slug", None))
    fallback = fallback_skill_icon(skill.name)
    if devicon_url:
        return {"type": "url", "primary": devicon_url, "fallback": fallback}
    return {"type": "url", "primary": fallback, "fallback": fallback}


@permission_required("activity_view", "activity_edit")
def country(request):
    if request.method == "GET":
        countries = Country.objects.all().order_by("name")
        states = State.objects.all().order_by("name")
        cities = City.objects.all().order_by("name")

        context = {
            "countries": countries,
            "states": states,
            "cities": cities,
            "country_enabled_count": countries.filter(status="Enabled").count(),
            "country_disabled_count": countries.filter(status="Disabled").count(),
            "state_enabled_count": states.filter(status="Enabled").count(),
            "state_disabled_count": states.filter(status="Disabled").count(),
            "city_enabled_count": cities.filter(status="Enabled").count(),
            "city_disabled_count": cities.filter(status="Disabled").count(),
        }

        return render(
            request,
            "dashboard/base_data/country.html",
            context,
        )
    if request.user.is_staff or request.user.has_perm("activity_edit"):
        if request.POST.get("mode") == "add_country":
            new_country = CountryForm(request.POST)
            if new_country.is_valid():
                country = new_country.save()
                country.slug = slugify(country.name)
                country.save()
                data = {"error": False, "message": "Country Added Successfully"}
            else:
                data = {"error": True, "message": new_country.errors["name"]}
            return HttpResponse(json.dumps(data))

        if request.POST.get("mode") == "edit_country":
            country = Country.objects.get(id=request.POST.get("id"))
            new_country = CountryForm(request.POST, instance=country)
            if new_country.is_valid():
                new_country.save()
                data = {"error": False, "message": "Country Updated Successfully"}
            else:
                data = {"error": True, "message": new_country.errors}
            return HttpResponse(json.dumps(data))
        if request.POST.get("mode") == "remove_country":
            country = Country.objects.filter(id=request.POST.get("id"))
            if country:
                country[0].delete()
                data = {"error": False, "message": "Country Removed Successfully"}
            else:
                data = {"error": True, "message": "Country Not found"}
            return HttpResponse(json.dumps(data))
    else:
        data = {"error": True, "message": "Only Admin Can create/edit country"}
        return HttpResponse(json.dumps(data))

    if request.POST.get("mode") == "get_states":
        country = Country.objects.filter(id=request.POST.get("c_id")).first()
        if not country:
            data = {"html": "", "slug": ""}
            return HttpResponse(json.dumps(data))
        states = State.objects.filter(country=country).order_by("name")
        state_items = []
        seen_states = set()
        for s in states:
            state_key = (s.name.lower(), s.country_id)
            if state_key in seen_states:
                continue
            seen_states.add(state_key)
            disabled_class = "disabled_ticket" if s.status == "Disabled" else ""
            status_class = "status-disabled" if s.status == "Disabled" else "status-enabled"
            toggle_icon = "fa-toggle-off" if s.status == "Disabled" else "fa-toggle-on"
            action_class = "edit" if s.status == "Disabled" else ""
            state_items.append(
                (
                    '<div class="ticket {disabled_class}">'
                    '<div class="ticket-info">'
                    '<div>'
                    '<a class="name_ticket" id="{status}" href="{id}">{name}</a>'
                    '<div class="ticket-meta">'
                    '<span class="badge job_count">{job_count} jobs</span>'
                    '</div>'
                    '</div>'
                    '<span class="status-badge {status_class}">{status_label}</span>'
                    '</div>'
                    '<div class="remove_ticket remove_states">'
                    '<a class="delete btn-icon" href="{id}" countryId="{country_id}" id="{status}"><i class="fa-solid fa-trash-can"></i></a>'
                    '</div>'
                    '<div class="actions_ticket">'
                    '<a class="{action_class}" href="{id}" countryId="{country_id}" id="{status}"><i class="fa-solid {toggle_icon}"></i></a>'
                    '</div>'
                    '</div>'
                ).format(
                    disabled_class=disabled_class,
                    status=s.status,
                    status_class=status_class,
                    status_label=s.status.title(),
                    id=s.id,
                    name=s.name,
                    job_count=s.get_no_of_jobposts().count(),
                    country_id=s.country.id,
                    action_class=action_class,
                    toggle_icon=toggle_icon,
                )
            )

        data = {"html": "".join(state_items), "slug": country.slug}
        return HttpResponse(json.dumps(data))

    if request.user.is_staff or request.user.has_perm("activity_edit"):
        if request.POST.get("mode") == "add_state":
            new_state = StateForm(request.POST)
            if new_state.is_valid():
                s = new_state.save()
                s.slug = slugify(s.name)
                s.save()
                data = {
                    "error": False,
                    "message": "State Added Successfully",
                    "id": s.id,
                    "status": s.status,
                    "name": s.name,
                }
            else:
                data = {"error": True, "message": new_state.errors}
            return HttpResponse(json.dumps(data))

        if request.POST.get("mode") == "edit_state":
            state = State.objects.get(id=request.POST.get("id"))
            new_state = StateForm(request.POST, instance=state)
            if new_state.is_valid():
                new_state.save()
                data = {"error": False, "message": "State Updated Successfully"}
            else:
                data = {"error": True, "message": new_state.errors}
            return HttpResponse(json.dumps(data))
        if request.POST.get("mode") == "remove_state":
            state = State.objects.filter(id=request.POST.get("id"))
            if state:
                state[0].delete()
                data = {"error": False, "message": "State Removed Successfully"}
            else:
                data = {"error": True, "message": "State Not found"}
            return HttpResponse(json.dumps(data))
    else:
        data = {"error": True, "message": "Only Admin Can create/edit country"}
        return HttpResponse(json.dumps(data))

    if request.POST.get("mode") == "get_cities":
        state = State.objects.filter(id=request.POST.get("s_id")).first()
        if not state:
            data = {"html": "", "country": "", "state_slug": ""}
            return HttpResponse(json.dumps(data))
        country = state.country.id
        cities = City.objects.filter(state=state).order_by("name")
        city_items = []
        seen_cities = set()
        for c in cities:
            city_key = (c.name.lower(), c.state_id)
            if city_key in seen_cities:
                continue
            seen_cities.add(city_key)
            disabled_class = "disabled_ticket" if c.status == "Disabled" else ""
            status_class = "status-disabled" if c.status == "Disabled" else "status-enabled"
            toggle_icon = "fa-toggle-off" if c.status == "Disabled" else "fa-toggle-on"
            action_class = "edit" if c.status == "Disabled" else ""
            view_url = reverse("job_locations", kwargs={"location": c.slug}) if c.slug else "#"
            city_items.append(
                (
                    '<div class="ticket {disabled_class}">'
                    '<div class="ticket-info">'
                    '<div>'
                    '<a class="name_ticket" id="{status}" href="{id}">{name}</a>'
                    '<div class="ticket-meta">'
                    '<span class="badge job_count">{job_count} jobs</span>'
                    '<a class="view_link" href="{view_url}" title="View public page" target="_blank"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>'
                    '<a class="add_other_city btn-icon" title="Add locality" id="{id}" data-state="{state_id}"><i class="fa-solid fa-plus"></i></a>'
                    '</div>'
                    '</div>'
                    '<span class="status-badge {status_class}">{status_label}</span>'
                    '</div>'
                    '<div class="remove_ticket remove_city">'
                    '<a class="delete btn-icon" href="{id}" id="{status}"><i class="fa-solid fa-trash-can"></i></a>'
                    '</div>'
                    '<div class="actions_ticket">'
                    '<a class="{action_class}" href="{id}" stateId="{state_id}" id="{status}"><i class="fa-solid {toggle_icon}"></i></a>'
                    '<span class="meta_title meta_data">{meta_title}</span>'
                    '<span class="meta_description meta_data">{meta_description}</span>'
                    '<span class="internship_meta_title meta_data">{internship_meta_title}</span>'
                    '<span class="internship_meta_description meta_data">{internship_meta_description}</span>'
                    '</div>'
                    '</div>'
                ).format(
                    disabled_class=disabled_class,
                    status=c.status,
                    status_class=status_class,
                    status_label=c.status.title(),
                    id=c.id,
                    name=c.name,
                    job_count=c.get_no_of_jobposts().count(),
                    state_id=c.state.id,
                    action_class=action_class,
                    toggle_icon=toggle_icon,
                    view_url=view_url,
                    meta_title=c.meta_title or "",
                    meta_description=c.meta_description or "",
                    internship_meta_title=c.internship_meta_title or "",
                    internship_meta_description=c.internship_meta_description or "",
                )
            )
        data = {"html": "".join(city_items), "country": country, "state_slug": state.slug}
        return HttpResponse(json.dumps(data))
    if request.POST.get("mode") == "get_city_info":
        city = City.objects.filter(id=request.POST.get("city")).first()
        if city:
            data = {
                "city": city.id,
                "country": city.state.country.id,
                "state": city.state.id,
                "slug": city.slug,
            }
            return HttpResponse(json.dumps(data))
        else:
            data = {}
            return HttpResponse(json.dumps(data))

    if request.user.is_staff or request.user.has_perm("activity_edit"):
        if request.POST.get("mode") == "add_city":
            new_city = CityForm(request.POST)
            if new_city.is_valid():
                c = new_city.save()
                c.slug = slugify(c.name)
                c.save()
                data = {
                    "error": False,
                    "message": "City Added Successfully",
                    "id": c.id,
                    "status": c.status,
                    "name": c.name,
                }
            else:
                data = {"error": True, "message": new_city.errors["name"]}
            return HttpResponse(json.dumps(data))

        if request.POST.get("mode") == "add_other_city":
            new_city = CityForm(request.POST)
            if new_city.is_valid():
                c = new_city.save()
                c.slug = slugify(c.name)
                c.save()
                data = {
                    "error": False,
                    "message": "City Added Successfully",
                    "id": c.id,
                    "status": c.status,
                    "name": c.name,
                }
            else:
                data = {"error": True, "message": new_city.errors["name"]}
            return HttpResponse(json.dumps(data))

        if request.POST.get("mode") == "edit_city":
            city = City.objects.get(id=request.POST.get("id"))
            new_city = CityForm(request.POST, instance=city)
            if new_city.is_valid():
                new_city.save()
                if State.objects.filter(id=request.POST.get("state")):
                    city.state = State.objects.filter(id=request.POST.get("state"))[0]
                if request.POST.get("meta_title"):
                    city.meta_title = request.POST.get("meta_title")
                if request.POST.get("meta_description"):
                    city.meta_description = request.POST.get("meta_description")
                if request.POST.get("internship_meta_title"):
                    city.internship_meta_title = request.POST.get(
                        "internship_meta_title"
                    )
                if request.POST.get("internship_meta_description"):
                    city.internship_meta_description = request.POST.get(
                        "internship_meta_description"
                    )
                if request.POST.get("page_content"):
                    city.page_content = request.POST.get("page_content")
                city.save()
                data = {"error": False, "message": "City Updated Successfully"}
            else:
                data = {"error": True, "message": new_city.errors}
            return HttpResponse(json.dumps(data))
        if request.POST.get("mode") == "remove_city":
            city = City.objects.filter(id=request.POST.get("id"))
            if city:
                city[0].delete()
                data = {"error": False, "message": "City Removed Successfully"}
            else:
                data = {"error": True, "message": "City Not Found"}
            return HttpResponse(json.dumps(data))
    else:
        data = {"error": True, "message": "Only Admin Can create/edit country"}
        return HttpResponse(json.dumps(data))

    if request.POST.get("mode") == "country_status":
        country = Country.objects.filter(id=request.POST.get("id")).first()
        if not country:
            data = {"error": True, "message": "Country Not Found"}
            return HttpResponse(json.dumps(data))
        if request.user.is_staff or request.user.has_perm("activity_edit"):
            if country.status == "Enabled":
                country.status = "Disabled"
                country.save()
                states = State.objects.filter(country_id=country.id)
                if states:
                    State.objects.filter(country_id=country.id).update(
                        status="Disabled"
                    )
                    City.objects.filter(state_id__in=states).update(status="Disabled")

                data = {"error": False, "message": "Country Disabled Successfully"}
                return HttpResponse(json.dumps(data))
            else:
                country.status = "Enabled"
                country.save()
                states = State.objects.filter(country_id=country.id)
                if states:
                    State.objects.filter(country_id=country.id).update(status="Enabled")
                    City.objects.filter(state_id__in=states).update(status="Enabled")

                data = {"error": False, "message": "Country Enabled Successfully"}
                return HttpResponse(json.dumps(data))
        else:
            data = {"error": True, "message": "Only Admin Can edit country status"}
            return HttpResponse(json.dumps(data))

    if request.POST.get("mode") == "state_status":
        country_status = False
        state = State.objects.filter(id=request.POST.get("id")).first()
        if not state:
            data = {"error": True, "message": "State Not Found"}
            return HttpResponse(json.dumps(data))
        if request.user.is_staff or request.user.has_perm("activity_edit"):
            if state.status == "Enabled":
                state.status = "Disabled"
                state.save()
                cities = state.state.all()
                if cities:
                    cities.update(status="Disabled")

                if not State.objects.filter(country=state.country, status="Enabled"):
                    if state.country.status != "Disabled":
                        state.country.status = "Disabled"
                        country_status = True
                        state.country.save()

                data = {
                    "error": False,
                    "message": "State Disabled Successfully",
                    "country_status": country_status,
                    "country_id": state.country.id,
                }
            else:
                state.status = "Enabled"
                state.save()
                state.country.status = "Enabled"
                state.country.save()
                cities = state.state.all()
                if cities:
                    cities.update(status="Enabled")

                data = {
                    "error": False,
                    "message": "State Enabled Successfully",
                    "country_status": country_status,
                    "country_id": state.country.id,
                }
            return HttpResponse(json.dumps(data))
        else:
            data = {"error": True, "message": "Only Admin Can create/edit country"}
            return HttpResponse(json.dumps(data))

    if request.POST.get("mode") == "city_status":
        state_status = False
        country_status = False
        city = City.objects.filter(id=request.POST.get("id")).first()
        if not city:
            data = {"error": True, "message": "City Not Found"}
            return HttpResponse(json.dumps(data))
        if request.user.is_staff or request.user.has_perm("activity_edit"):
            if city.status == "Enabled":
                city.status = "Disabled"
                city.save()

                if not City.objects.filter(state=city.state, status="Enabled"):
                    if city.state.status != "Disabled":
                        city.state.status = "Disabled"
                        state_status = True
                        city.state.save()

                    if not State.objects.filter(
                        country=city.state.country, status="Enabled"
                    ):
                        if city.state.country.status != "Disabled":
                            city.state.country.status = "Disabled"
                            country_status = True
                            city.state.country.save()

                data = {
                    "error": False,
                    "message": "City Disabled Successfully",
                    "state_status": state_status,
                    "country_status": country_status,
                    "state_id": city.state.id,
                    "country_id": city.state.country.id,
                }
                return HttpResponse(json.dumps(data))
            else:
                city.status = "Enabled"
                city.save()
                city.state.status = "Enabled"
                city.state.save()
                if city.state.country.status == "Disabled":
                    city.state.country.status = "Enabled"
                    city.state.country.save()
                data = {
                    "error": False,
                    "message": "City Enabled Successfully",
                    "state_status": state_status,
                    "country_status": country_status,
                    "state_id": city.state.id,
                    "country_id": city.state.country.id,
                }
                return HttpResponse(json.dumps(data))
        else:
            data = {"error": True, "message": "Only Admin Can create/edit country"}
            return HttpResponse(json.dumps(data))



@permission_required("activity_view", "activity_edit")
def locations(request, status):
    # Get base queryset based on status
    if status == "active":
        locations_qs = (
            City.objects.filter(status="Enabled")
            .annotate(num_posts=Count("locations"))
            .prefetch_related("state", "state__country")
        )
    else:
        locations_qs = (
            City.objects.filter(status="Disabled")
            .annotate(num_posts=Count("locations"))
            .prefetch_related("state", "state__country")
        )
    
    # Handle search from both GET and POST
    search_term = ""
    sort_by = request.GET.get("sort", "name")  # Default sort by name
    
    if request.method == "POST":
        if request.POST.get("mode") == "remove_city":
            if request.user.is_staff or request.user.has_perm("activity_edit"):
                city_id = request.POST.get("id")
                if city_id:
                    city = City.objects.filter(id=city_id).first()
                    if city:
                        # Check for active job posts using this city
                        active_job_count = JobPost.objects.filter(
                            location=city, 
                            status__in=["Live", "Published"]
                        ).count()
                        
                        if active_job_count > 0:
                            data = {
                                "error": True, 
                                "message": f"Cannot delete city. {active_job_count} active job post(s) are using this location. Please reassign or deactivate these jobs first."
                            }
                        else:
                            city.delete()
                            data = {"error": False, "message": "City Removed Successfully"}
                    else:
                        data = {"error": True, "message": "City Not Found"}
                else:
                    data = {"error": True, "message": "Invalid city ID"}
            else:
                data = {"error": True, "message": "Permission denied"}
            return HttpResponse(json.dumps(data))
            
        elif request.POST.get("mode") == "edit":
            if request.user.is_staff or request.user.has_perm("activity_edit"):
                city_id = request.POST.get("id")
                if not city_id:
                    data = {"error": True, "message": "City ID is required"}
                    return HttpResponse(json.dumps(data))
                
                city = City.objects.filter(id=int(city_id)).first()
                if not city:
                    data = {"error": True, "message": "City Not Found"}
                    return HttpResponse(json.dumps(data))
                
                form = CityForm(request.POST, instance=city)
                is_valid = True
                
                # Validate JSON meta field if provided
                if request.POST.get("meta"):
                    try:
                        json.loads(request.POST.get("meta"))
                    except (json.JSONDecodeError, ValueError) as e:
                        form.add_error("meta", f"Enter Valid JSON Format - {str(e)}")
                        is_valid = False
                
                if form.is_valid() and is_valid:
                    # Check if state change is valid
                    if request.POST.get("state"):
                        try:
                            new_state = State.objects.get(id=request.POST.get("state"), status="Enabled")
                            city.state = new_state
                        except State.DoesNotExist:
                            data = {"error": True, "message": "Invalid state selected", "id": city_id}
                            return HttpResponse(json.dumps(data))
                    
                    form.save()
                    
                    # Update additional fields
                    if request.POST.get("page_content"):
                        city.page_content = request.POST.get("page_content")
                    if request.POST.get("internship_page_content"):
                        city.internship_page_content = request.POST.get("internship_page_content")
                    if request.POST.get("meta"):
                        city.meta = json.loads(request.POST.get("meta"))
                    
                    city.save()
                    data = {"error": False, "message": "City Updated Successfully"}
                else:
                    data = {
                        "error": True,
                        "message": form.errors,
                        "id": city_id,
                    }
            else:
                data = {"error": True, "message": "Permission denied"}
            return HttpResponse(json.dumps(data))
        
        elif request.POST.get("mode") == "move_jobs":
            if request.user.is_staff or request.user.has_perm("activity_edit"):
                from_city_id = request.POST.get("from_city_id")
                to_city_id = request.POST.get("to_city_id")

                try:
                    from_city = City.objects.get(id=from_city_id)
                    to_city = City.objects.get(id=to_city_id)

                    # Get all job posts that have the source city
                    job_posts = JobPost.objects.filter(location=from_city)
                    moved_count = 0

                    for job_post in job_posts:
                        # Remove the old city and add the new one
                        job_post.location.remove(from_city)
                        job_post.location.add(to_city)
                        moved_count += 1

                    data = {
                        "error": False,
                        "message": f"Successfully moved {moved_count} jobs from '{from_city.name}' to '{to_city.name}'",
                        "moved_count": moved_count,
                    }
                except City.DoesNotExist:
                    data = {
                        "error": True,
                        "message": "Invalid city selected",
                    }
                except Exception as e:
                    data = {
                        "error": True,
                        "message": f"Error moving jobs: {str(e)}",
                    }
            else:
                data = {"error": True, "message": "Permission denied"}
            return HttpResponse(json.dumps(data))
        
        # Handle search via POST
        elif request.POST.get("search"):
            search_term = request.POST.get("search").strip()
    
    # Handle search via GET (for pagination links)
    if not search_term:
        search_term = request.GET.get("search", "").strip()
    
    # Apply search filter
    if search_term:
        locations_qs = locations_qs.filter(name__icontains=search_term)
    
    # Apply sorting
    if sort_by == "name":
        locations_qs = locations_qs.order_by("name")
    elif sort_by == "job_posts_asc":
        locations_qs = locations_qs.order_by("num_posts", "name")
    elif sort_by == "job_posts_desc":
        locations_qs = locations_qs.order_by("-num_posts", "name")
    else:
        locations_qs = locations_qs.order_by("name")
    
    # Pagination
    items_per_page = 100
    paginator = Paginator(locations_qs, items_per_page)
    page_number = request.GET.get("page", 1)
    
    try:
        page_obj = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.get_page(1)
    
    # Get pagination context
    prev_page, previous_page, aft_page, after_page = get_prev_after_pages_count(
        page_obj.number, paginator.num_pages
    )
    
    # Get enabled cities for dropdown
    cities = City.objects.filter(status="Enabled").prefetch_related("state", "state__country").order_by("name")
    
    # Get all states for the state dropdown in edit form
    states = State.objects.filter(status="Enabled").prefetch_related("country").order_by("country__name", "name")
    
    context = {
        "locations": page_obj,
        "cities": cities,
        "states": states,
        "aft_page": aft_page,
        "after_page": after_page,
        "prev_page": prev_page,
        "previous_page": previous_page,
        "current_page": page_obj.number,
        "last_page": paginator.num_pages,
        "status": status,
        "search_term": search_term,
        "search_value": search_term,  # For backward compatibility
        "sort_by": sort_by,
    }
    
    return render(request, "dashboard/locations.html", context)



@permission_required("activity_view", "activity_edit")
def tech_skills(request):
    if request.method == "GET":
        skills_qs = Skill.objects.all().order_by("name")

        if request.GET.get("search"):
            skills_qs = skills_qs.filter(name__icontains=request.GET.get("search"))
        status = request.GET.get("status")
        filtered_skills = skills_qs
        if status:
            if status == "active":
                filtered_skills = filtered_skills.filter(status="Active")
            elif status == "inactive":
                filtered_skills = filtered_skills.filter(status="InActive")
            else:
                filtered_skills = filtered_skills.filter(skill_type=status)

        metrics = {
            "total": skills_qs.count(),
            "active": skills_qs.filter(status="Active").count(),
            "inactive": skills_qs.filter(status="InActive").count(),
            "it": skills_qs.filter(skill_type="it").count(),
            "non_it": skills_qs.filter(skill_type="non-it").count(),
            "other": skills_qs.filter(skill_type="other").count(),
        }

        filters = [
            {"key": "active", "label": "Active", "count": metrics["active"]},
            {"key": "inactive", "label": "Inactive", "count": metrics["inactive"]},
            {"key": "it", "label": "IT", "count": metrics["it"]},
            {"key": "non-it", "label": "Non-IT", "count": metrics["non_it"]},
            {"key": "other", "label": "Other", "count": metrics["other"]},
        ]

        items_per_page = 20
        filtered_count = filtered_skills.count()
        no_pages = int(math.ceil(float(filtered_count) / items_per_page)) if filtered_count else 1

        if (
            "page" in request.GET
            and bool(re.search(r"[0-9]", request.GET.get("page")))
            and int(request.GET.get("page")) > 0
        ):
            if int(request.GET.get("page")) > (no_pages + 2):
                return HttpResponseRedirect(reverse("dashboard:tech_skills"))
            else:
                page = int(request.GET.get("page"))
        else:
            page = 1

        skills = list(filtered_skills[(page - 1) * items_per_page : page * items_per_page])
        for skill in skills:
            icon_info = resolve_skill_icon(skill)
            if icon_info['type'] == 'class':
                skill.icon_is_class = True
                skill.icon_class = icon_info['primary']
                skill.icon_url = None
                skill.icon_fallback = icon_info['fallback']
            else:
                skill.icon_is_class = False
                skill.icon_class = ''
                skill.icon_url = icon_info['primary']
                skill.icon_fallback = icon_info['fallback']
            if skill.meta:
                try:
                    skill.meta_text = json.dumps(skill.meta, indent=2, sort_keys=True)
                except (TypeError, ValueError):
                    skill.meta_text = str(skill.meta)
            else:
                skill.meta_text = ""
        prev_page, previous_page, aft_page, after_page = get_prev_after_pages_count(
            page, no_pages
        )
        return render(
            request,
            "dashboard/base_data/technical_skills.html",
            {
                "search": request.GET.get("search"),
                "status": status,
                "skills": skills,
                "metrics": metrics,
                "filters": filters,
                "aft_page": aft_page,
                "after_page": after_page,
                "prev_page": prev_page,
                "previous_page": previous_page,
                "current_page": page,
                "last_page": no_pages,
                "skill_types": SKILL_TYPE,
                "total_results": filtered_count,
            },
        )
    else:
        if request.user.is_staff == "Admin" or request.user.has_perm("activity_edit"):
            if request.POST.get("mode") == "add_skill":
                new_skill = SkillForm(request.POST, request.FILES)
                if new_skill.is_valid():
                    new_skill = new_skill.save(commit=False)
                    if request.FILES and request.FILES.get("icon"):
                        file_path = get_aws_file_path(
                            request.FILES.get("icon"),
                            "technology/icons/",
                            slugify(request.POST.get("name")),
                        )
                        new_skill.icon = file_path
                    new_skill.status = "InActive"
                    new_skill.skill_type = request.POST.get("skill_type")
                    with disable_haystack_signals():
                        new_skill.save()
                    data = {"error": False, "message": "Skill Added Successfully"}
                else:
                    data = {"error": True, "message": new_skill.errors}
                return HttpResponse(json.dumps(data))
            if request.POST.get("mode") == "edit_skill":
                skill = Skill.objects.filter(id=request.POST.get("id")).first()
                if skill:
                    new_skill = SkillForm(request.POST, request.FILES, instance=skill)
                    try:
                        if request.POST.get("meta"):
                            json.loads(request.POST.get("meta"))
                        valid = True
                    except BaseException as e:
                        new_skill.errors["meta"] = "Enter Valid Json Format - " + str(e)
                        valid = False
                    if new_skill.is_valid() and valid:
                        edit_tech_skills(skill, request)
                        data = {"error": False, "message": "Skill Updated Successfully"}
                        return HttpResponse(json.dumps(data))
                    else:
                        data = {"error": True, "response": new_skill.errors}
                    return HttpResponse(json.dumps(data))
                else:
                    data = {
                        "error": True,
                        "message": "Skill Not Found",
                        "page": (
                            request.POST.get("page") if request.POST.get("page") else 1
                        ),
                    }
                    return HttpResponse(json.dumps(data))
        else:
            data = {
                "error": True,
                "message": "Only Admin can add/edit Technical Skill",
                "page": request.POST.get("page") if request.POST.get("page") else 1,
            }
            return HttpResponse(json.dumps(data))



def edit_tech_skills(skill, request):
    if request.FILES.get("icon"):
        if skill.icon:
            url = str(skill.icon).split("cdn.careerlite.com")[-1:]
            AWS().cloudfront_invalidate(paths=url)
        file_path = get_aws_file_path(
            request.FILES.get("icon"),
            "technology/icons/",
            slugify(request.POST.get("name")),
        )
        skill.icon = file_path
    skill.name = request.POST.get("name")
    if request.POST.get("slug"):
        skill.slug = request.POST.get("slug")
    if request.POST.get("skill_type"):
        skill.skill_type = request.POST.get("skill_type")
    if request.POST.get("page_content"):
        skill.page_content = request.POST.get("page_content")
    if request.POST.get("meta"):
        skill.meta = json.loads(request.POST.get("meta"))
    with disable_haystack_signals():
        skill.save()



@permission_required("activity_edit")
def delete_skill(request, skill_id):
    skill = Skill.objects.filter(id=skill_id)
    if skill:
        skill.delete()
        data = {
            "error": False,
            "message": "Skill Removed Successfully",
            "path": request.path,
        }
    else:
        data = {"error": True, "message": "Skill Not Found", "path": request.path}
    return HttpResponse(json.dumps(data))



@permission_required("activity_edit")
def skill_status(request, skill_id):
    skill = Skill.objects.filter(id=skill_id).first()
    if skill:
        skill.status = "InActive" if skill.status == "Active" else "Active"
        skill.save()
        data = {"error": False, "response": "Skill Status Changed Successfully"}
    else:
        data = {"error": True, "response": "skill not exists"}
    return HttpResponse(json.dumps(data))




@permission_required("activity_view", "activity_edit")
def languages(request):
    if request.method == "GET":
        languages_qs = Language.objects.all().order_by("name")
        total_languages = languages_qs.count()
        if request.GET.get("search"):
            languages_qs = languages_qs.filter(
                name__icontains=request.GET.get("search")
            )

        filtered_count = languages_qs.count()
        items_per_page = 20
        no_pages = (
            int(math.ceil(float(filtered_count) / items_per_page))
            if filtered_count
            else 1
        )

        if (
            "page" in request.GET
            and bool(re.search(r"[0-9]", request.GET.get("page")))
            and int(request.GET.get("page")) > 0
        ):
            if int(request.GET.get("page")) > (no_pages + 2):
                return HttpResponseRedirect(reverse("dashboard:languages"))
            else:
                page = int(request.GET.get("page"))
        else:
            page = 1

        languages = languages_qs[(page - 1) * items_per_page : page * items_per_page]
        prev_page, previous_page, aft_page, after_page = get_prev_after_pages_count(
            page, no_pages
        )
        search_value = request.GET.get("search") if request.GET.get("search") else None
        return render(
            request,
            "dashboard/base_data/languages.html",
            {
                "search_value": search_value,
                "languages": languages,
                "filtered_count": filtered_count,
                "total_languages": total_languages,
                "aft_page": aft_page,
                "after_page": after_page,
                "prev_page": prev_page,
                "previous_page": previous_page,
                "current_page": page,
                "last_page": no_pages,
            },
        )

    if request.user.user_type == "Admin" or request.user.has_perm("activity_edit"):

        if request.POST.get("mode") == "add_language":
            new_language = LanguageForm(request.POST)
            if new_language.is_valid():
                new_language.save()
                data = {"error": False, "message": "Language Added Successfully"}
            else:
                data = {"error": True, "message": new_language.errors["name"]}
            return HttpResponse(json.dumps(data))

        if request.POST.get("mode") == "edit_language":
            language = Language.objects.get(id=request.POST.get("id"))
            new_language = LanguageForm(request.POST, instance=language)
            if new_language.is_valid():
                new_language.save()
                data = {
                    "error": False,
                    "message": "Language Updated Successfully",
                    "page": request.POST.get("page") if request.POST.get("page") else 1,
                }
            else:
                data = {
                    "error": True,
                    "message": new_language.errors["name"],
                    "page": request.POST.get("page") if request.POST.get("page") else 1,
                }
            return HttpResponse(json.dumps(data))
    else:
        data = {
            "error": True,
            "message": "Only Admin can add/edit Qualification",
            "page": request.POST.get("page") if request.POST.get("page") else 1,
        }
        return HttpResponse(json.dumps(data))



@permission_required("activity_edit")
def delete_language(request, language_id):
    Language.objects.get(id=language_id).delete()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))



@permission_required("activity_view", "activity_edit")
def qualifications(request):
    if request.method == "GET":
        qualifications = Qualification.objects.all().order_by("name")
        if request.GET.get("search"):
            qualifications = qualifications.filter(
                name__icontains=request.GET.get("search")
            )
        if request.GET.get("status") == "Active":
            qualifications = qualifications.filter(status="Active")
        elif request.GET.get("status") == "InActive":
            qualifications = qualifications.filter(status="InActive")

        items_per_page = 10
        no_pages = int(math.ceil(float(qualifications.count()) / items_per_page))

        if (
            "page" in request.GET
            and bool(re.search(r"[0-9]", request.GET.get("page")))
            and int(request.GET.get("page")) > 0
        ):
            if int(request.GET.get("page")) > (no_pages + 2):
                return HttpResponseRedirect(reverse("dashboard:qualifications"))
            page = int(request.GET.get("page"))
        else:
            page = 1

        qualifications = qualifications[
            (page - 1) * items_per_page : page * items_per_page
        ]
        prev_page, previous_page, aft_page, after_page = get_prev_after_pages_count(
            page, no_pages
        )
        status = request.GET.get("status") if request.GET.get("status") else None
        search = request.GET.get("search") if request.GET.get("search") else None
        return render(
            request,
            "dashboard/base_data/qualifications.html",
            {
                "status": status,
                "qualifications": qualifications,
                "aft_page": aft_page,
                "after_page": after_page,
                "prev_page": prev_page,
                "previous_page": previous_page,
                "current_page": page,
                "last_page": no_pages,
                "search": search,
            },
        )
    if request.user.is_staff or request.user.has_perm("activity_edit"):
        if request.POST.get("mode") == "add_qualification":
            new_qualification = QualificationForm(request.POST)
            if new_qualification.is_valid():
                new_qualification.save()
                data = {"error": False, "message": "Qualification Added Successfully"}
            else:
                data = {"error": True, "message": new_qualification.errors["name"]}
            return HttpResponse(json.dumps(data))

        if request.POST.get("mode") == "edit_qualification":
            qualification = Qualification.objects.get(id=request.POST.get("id"))
            new_qualification = QualificationForm(request.POST, instance=qualification)
            if new_qualification.is_valid():
                new_qualification.save()
                data = {
                    "error": False,
                    "message": "Qualification Updated Successfully",
                    "page": request.POST.get("page") if request.POST.get("page") else 1,
                }
            else:
                data = {
                    "error": True,
                    "message": new_qualification.errors["name"],
                    "page": request.POST.get("page") if request.POST.get("page") else 1,
                }
            return HttpResponse(json.dumps(data))
    else:
        data = {
            "error": True,
            "message": "Only Admin can add/edit Qualification",
            "page": request.POST.get("page") if request.POST.get("page") else 1,
        }
        return HttpResponse(json.dumps(data))



@permission_required("activity_edit")
def delete_qualification(request, qualification_id):
    Qualification.objects.get(id=qualification_id).delete()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))



@permission_required("activity_edit")
def qualification_status(request, qualification_id):
    qualification = Qualification.objects.filter(id=qualification_id).first()
    if qualification:
        qualification.status = (
            "InActive" if qualification.status == "Active" else "Active"
        )
        qualification.save()
        data = {
            "error": False,
            "response": "Qualification Status Changed Successfully",
            "page": request.POST.get("page") if request.POST.get("page") else 1,
        }
    else:
        data = {
            "error": True,
            "response": "Qualification not exists",
            "page": request.POST.get("page") if request.POST.get("page") else 1,
        }
    return HttpResponse(json.dumps(data))



@permission_required("activity_view", "activity_edit")
def industries(request):
    if request.method == "GET":
        industries = Industry.objects.all().order_by("name")
        if request.GET.get("search"):
            industries = industries.filter(name__icontains=request.GET.get("search"))
        if request.GET.get("status") == "active":
            industries = industries.filter(status="Active")
        elif request.GET.get("status") == "inactive":
            industries = industries.filter(status="InActive")

        items_per_page = 15
        no_pages = int(math.ceil(float(industries.count()) / items_per_page))

        if (
            "page" in request.GET
            and bool(re.search(r"[0-9]", request.GET.get("page")))
            and int(request.GET.get("page")) > 0
        ):
            if int(request.GET.get("page")) > (no_pages + 2):
                return HttpResponseRedirect(reverse("dashboard:industries"))
            page = int(request.GET.get("page"))
        else:
            page = 1

        industries = industries[(page - 1) * items_per_page : page * items_per_page]
        prev_page, previous_page, aft_page, after_page = get_prev_after_pages_count(
            page, no_pages
        )
        status = request.GET.get("status") if request.GET.get("status") else None
        search = request.GET.get("search") if request.GET.get("search") else None

        # Get all active industries for the transfer dropdown
        all_active_industries = Industry.objects.filter(status="Active").order_by("name")

        return render(
            request,
            "dashboard/base_data/industry.html",
            {
                "status": status,
                "search": search,
                "industries": industries,
                "all_active_industries": all_active_industries,
                "aft_page": aft_page,
                "after_page": after_page,
                "prev_page": prev_page,
                "previous_page": previous_page,
                "current_page": page,
                "last_page": no_pages,
            },
        )

    if request.method == "POST":
        if request.user.is_staff or request.user.has_perm("activity_edit"):
            if request.POST.get("mode") == "add_industry":
                new_industry = IndustryForm(request.POST)
                if new_industry.is_valid():
                    new_industry.save()
                    data = {"error": False, "message": "Industry Added Successfully"}
                else:
                    data = {"error": True, "message": new_industry.errors["name"]}
                return HttpResponse(json.dumps(data))

            if request.POST.get("mode") == "edit_industry":
                industry = Industry.objects.get(id=request.POST.get("id"))
                new_industry = IndustryForm(request.POST, instance=industry)
                if new_industry.is_valid():
                    new_industry.save()
                    if request.POST.get("meta_title"):
                        industry.meta_title = request.POST.get("meta_title")
                    if request.POST.get("meta_description"):
                        industry.meta_description = request.POST.get("meta_description")
                    if request.POST.get("page_content"):
                        industry.page_content = request.POST.get("page_content")
                    industry.save()
                    data = {
                        "error": False,
                        "message": "Industry Updated Successfully",
                        "page": request.POST.get("page") if request.POST.get("page") else 1,
                    }
                else:
                    data = {
                        "error": True,
                        "message": new_industry.errors,
                        "page": request.POST.get("page") if request.POST.get("page") else 1,
                    }
                return HttpResponse(json.dumps(data))
            
            if request.POST.get("mode") == "move_jobs":
                from_industry_id = request.POST.get("from_industry_id")
                to_industry_id = request.POST.get("to_industry_id")

                try:
                    from_industry = Industry.objects.get(id=from_industry_id)
                    to_industry = Industry.objects.get(id=to_industry_id)

                    # Get all job posts that have the source industry
                    job_posts = JobPost.objects.filter(industry=from_industry)
                    moved_count = 0

                    for job_post in job_posts:
                        # Remove the old industry and add the new one
                        job_post.industry.remove(from_industry)
                        job_post.industry.add(to_industry)
                        moved_count += 1

                    data = {
                        "error": False,
                        "message": f"Successfully moved {moved_count} jobs from '{from_industry.name}' to '{to_industry.name}'",
                        "moved_count": moved_count,
                        "page": request.POST.get("page") if request.POST.get("page") else 1,
                    }
                except Industry.DoesNotExist:
                    data = {
                        "error": True,
                        "message": "Invalid industry selected",
                        "page": request.POST.get("page") if request.POST.get("page") else 1,
                    }
                except Exception as e:
                    data = {
                        "error": True,
                        "message": f"Error moving jobs: {str(e)}",
                        "page": request.POST.get("page") if request.POST.get("page") else 1,
                    }
                return HttpResponse(json.dumps(data))
        else:
            data = {
                "error": True,
                "message": "Only Admin can add/edit Industry",
                "page": request.POST.get("page") if request.POST.get("page") else 1,
            }
            return HttpResponse(json.dumps(data))



@permission_required("activity_edit")
def delete_industry(request, industry_id):
    Industry.objects.get(id=industry_id).delete()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))




@permission_required("activity_edit")
def industry_status(request, industry_id):
    industry = Industry.objects.filter(id=industry_id).first()
    if industry:
        industry.status = "InActive" if industry.status == "Active" else "Active"
        industry.save()
        data = {
            "error": False,
            "response": "Industry Status Changed Successfully",
            "page": request.POST.get("page") if request.POST.get("page") else 1,
        }
    else:
        data = {
            "error": True,
            "response": "Industry not exists",
            "page": request.POST.get("page") if request.POST.get("page") else 1,
        }
    return HttpResponse(json.dumps(data))



@permission_required("activity_view", "activity_edit")
def functional_area(request):
    if request.method == "GET":
        functional_areas = FunctionalArea.objects.all().order_by("name")
        if request.GET.get("search"):
            functional_areas = functional_areas.filter(
                name__icontains=request.GET.get("search")
            )
        if request.GET.get("status") == "active":
            functional_areas = functional_areas.filter(status="Active")
        elif request.GET.get("status") == "inactive":
            functional_areas = functional_areas.filter(status="InActive")

        items_per_page = 10
        no_pages = int(math.ceil(float(functional_areas.count()) / items_per_page))

        if (
            "page" in request.GET
            and bool(re.search(r"[0-9]", request.GET.get("page")))
            and int(request.GET.get("page")) > 0
        ):
            if int(request.GET.get("page")) > (no_pages + 2):
                return HttpResponseRedirect(reverse("dashboard:functional_area"))
            page = int(request.GET.get("page"))
        else:
            page = 1

        functional_areas = functional_areas[
            (page - 1) * items_per_page : page * items_per_page
        ]
        prev_page, previous_page, aft_page, after_page = get_prev_after_pages_count(
            page, no_pages
        )
        status = request.GET.get("status") if request.GET.get("status") else None
        search = request.GET.get("search") if request.GET.get("search") else None
        return render(
            request,
            "dashboard/base_data/functional_area.html",
            {
                "status": status,
                "search": search,
                "functional_areas": functional_areas,
                "aft_page": aft_page,
                "after_page": after_page,
                "prev_page": prev_page,
                "previous_page": previous_page,
                "current_page": page,
                "last_page": no_pages,
            },
        )

    if request.method == "POST":
        if request.user.is_staff or request.user.has_perm("activity_edit"):
            if request.POST.get("mode") == "add_functional_area":
                new_functional_area = FunctionalAreaForm(request.POST)
                if new_functional_area.is_valid():
                    new_functional_area.save()
                    data = {"error": False, "message": "Functional Area Added Successfully"}
                else:
                    data = {"error": True, "message": new_functional_area.errors["name"]}
                return HttpResponse(json.dumps(data))

            if request.POST.get("mode") == "edit_functional_area":
                functional_area = FunctionalArea.objects.get(id=request.POST.get("id"))
                new_functional_area = FunctionalAreaForm(
                    request.POST, instance=functional_area
                )
                if new_functional_area.is_valid():
                    new_functional_area.save()
                    data = {
                        "error": False,
                        "message": "Functional Area Updated Successfully",
                        "page": request.POST.get("page") if request.POST.get("page") else 1,
                    }
                else:
                    data = {
                        "error": True,
                        "message": new_functional_area.errors["name"],
                        "page": request.POST.get("page") if request.POST.get("page") else 1,
                    }
                return HttpResponse(json.dumps(data))
        else:
            data = {
                "error": True,
                "message": "Only Admin can add/edit Functional Area",
                "page": request.POST.get("page") if request.POST.get("page") else 1,
            }
            return HttpResponse(json.dumps(data))



@permission_required("activity_edit")
def delete_functional_area(request, functional_area_id):
    FunctionalArea.objects.get(id=functional_area_id).delete()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))



@permission_required("activity_edit")
def functional_area_status(request, functional_area_id):
    functional_area = FunctionalArea.objects.filter(id=functional_area_id).first()
    if functional_area:
        functional_area.status = (
            "InActive" if functional_area.status == "Active" else "Active"
        )
        functional_area.save()
        data = {
            "error": False,
            "response": "Functional Area Status Changed Successfully",
            "page": request.POST.get("page") if request.POST.get("page") else 1,
        }
    else:
        data = {
            "error": True,
            "response": "Functional Area not exists",
            "page": request.POST.get("page") if request.POST.get("page") else 1,
        }
    return HttpResponse(json.dumps(data))

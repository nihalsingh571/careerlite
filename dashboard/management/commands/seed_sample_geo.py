import random
from contextlib import contextmanager
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.utils import timezone
from django.utils.text import slugify

from peeldb.models import (
    City,
    Company,
    Country,
    FunctionalArea,
    Industry,
    InterviewLocation,
    JobPost,
    Keyword,
    Qualification,
    Skill,
    State,
    User,
)



@contextmanager
def disable_haystack_signals():
    disconnected = []
    for signal in (post_save, post_delete):
        for receiver_ref, receiver, *_ in list(signal.receivers):
            func = None
            if hasattr(receiver_ref, '__call__'):
                func = receiver_ref()
            if func is None and hasattr(receiver, '__call__'):
                func = receiver()
            if func is None:
                continue
            module = getattr(func, '__module__', '')
            if module.startswith('haystack'):
                signal.disconnect(func)
                disconnected.append((signal, func))
    try:
        yield
    finally:
        for signal, func in disconnected:
            try:
                signal.connect(func)
            except Exception:
                pass


COUNTRY_DATA = {
    "Germany": {
        "states": {
            "Bavaria": ["Munich", "Nuremberg"],
            "Berlin": ["Berlin", "Potsdam"],
            "Hamburg": ["Hamburg", "Lübeck"],
            "Hesse": ["Frankfurt", "Wiesbaden"],
            "Saxony": ["Dresden", "Leipzig"],
        }
    },
    "China": {
        "states": {
            "Guangdong": ["Guangzhou", "Shenzhen"],
            "Beijing": ["Beijing", "Tongzhou"],
            "Shanghai": ["Shanghai", "Pudong"],
            "Zhejiang": ["Hangzhou", "Ningbo"],
            "Sichuan": ["Chengdu", "Mianyang"],
        }
    },
    "Japan": {
        "states": {
            "Tokyo": ["Shinjuku", "Shibuya"],
            "Osaka": ["Osaka", "Sakai"],
            "Kanagawa": ["Yokohama", "Kawasaki"],
            "Aichi": ["Nagoya", "Toyota"],
            "Hokkaido": ["Sapporo", "Hakodate"],
        }
    },
}


class Command(BaseCommand):
    help = (
        "Seed sample geography data (countries, states, cities) and demo jobs "
        "for Germany, China, and Japan."
    )

    def handle(self, *args, **options):
        with disable_haystack_signals():
            with transaction.atomic():
                user = self._get_or_create_demo_recruiter()
                company = self._get_or_create_demo_company()
                if user.company_id != company.id:
                    user.company = company
                    user.save(update_fields=["company"])
                industry = self._get_or_create_industry()
                functional_area = self._get_or_create_functional_area()
                qualification = self._get_or_create_qualification()
                skill = self._get_or_create_skill()
                keyword = self._get_or_create_keyword()
                interview_location = self._get_or_create_interview_location()

                countries_seeded = []
                states_seeded = 0
                cities_seeded = 0
                jobs_seeded = 0

                for country_name, data in COUNTRY_DATA.items():
                    country = self._get_or_create_country(country_name)
                    countries_seeded.append(country.name)

                    for state_name, cities in data["states"].items():
                        state = self._get_or_create_state(country, state_name)
                        states_seeded += 1

                        for city_name in cities:
                            city = self._get_or_create_city(state, city_name)
                            cities_seeded += 1
                            jobs_seeded += self._get_or_create_city_jobs(
                                user=user,
                                company=company,
                                industry=industry,
                                functional_area=functional_area,
                                qualification=qualification,
                                skill=skill,
                                keyword=keyword,
                                interview_location=interview_location,
                                country=country,
                                state=state,
                                city=city,
                            )

        self.stdout.write(self.style.SUCCESS("Seed summary"))
        self.stdout.write(f"  Countries processed: {len(countries_seeded)}")
        self.stdout.write(f"  States ensured: {states_seeded}")
        self.stdout.write(f"  Cities ensured: {cities_seeded}")
        self.stdout.write(f"  Job posts ensured: {jobs_seeded}")

    # ------------------------------------------------------------------ helpers

    def _get_or_create_demo_recruiter(self):
        user, created = User.objects.get_or_create(
            email="demo.recruiter@careerlite.com",
            defaults={
                "username": "demo_recruiter",
                "first_name": "Demo",
                "last_name": "Recruiter",
                "user_type": "RR",
                "photo": "https://cdn.careerlite.com/static/default-user.png",
                "is_active": True,
                "is_staff": True,
                "registered_from": "Email",
            },
        )
        if created:
            user.set_password("demo1234")
            user.save()
        return user

    def _get_or_create_demo_company(self):
        company, _ = Company.objects.get_or_create(
            slug="careerlite-demo-company",
            defaults={
                "name": "Careerlite Demo Company",
                "address": "123 Innovation Way, Remote",
                "profile": "Demo company used for showcasing the dashboard data.",
                "phone_number": "+1-555-0100",
                "company_type": "Company",
                "meta_title": "Careerlite Demo Company",
                "meta_description": "Demo company created for local development data.",
                "email": "hello@careerlite-demo.com",
            },
        )
        return company

    def _get_or_create_industry(self):
        industry, _ = Industry.objects.get_or_create(
            slug="technology",
            defaults={
                "name": "Technology",
                "status": "Enabled",
                "meta_title": "Technology jobs",
                "meta_description": "Technology industry demo data.",
            },
        )
        return industry

    def _get_or_create_functional_area(self):
        area, _ = FunctionalArea.objects.get_or_create(
            slug="software-development",
            defaults={
                "name": "Software Development",
                "status": "Enabled",
            },
        )
        return area

    def _get_or_create_qualification(self):
        qualification, _ = Qualification.objects.get_or_create(
            slug="bachelors-degree",
            defaults={
                "name": "Bachelor's Degree",
                "status": "Enabled",
            },
        )
        return qualification

    def _get_or_create_skill(self):
        skill, _ = Skill.objects.get_or_create(
            slug="software-engineering",
            defaults={
                "name": "Software Engineering",
                "status": "Enabled",
                "icon": "fa-solid fa-code",
                "skill_type": "it",
            },
        )
        return skill

    def _get_or_create_keyword(self):
        keyword, _ = Keyword.objects.get_or_create(name="software")
        return keyword

    def _get_or_create_interview_location(self):
        location, _ = InterviewLocation.objects.get_or_create(
            venue_details="Main Campus - Virtual Interview Centre",
            defaults={"show_location": False},
        )
        return location

    def _get_or_create_country(self, name):
        country, created = Country.objects.get_or_create(
            name=name, defaults={"slug": slugify(name), "status": "Enabled"}
        )
        if created:
            return country

        updated = False
        if country.slug != slugify(name):
            country.slug = slugify(name)
            updated = True
        if country.status != "Enabled":
            country.status = "Enabled"
            updated = True
        if updated:
            country.save()
        return country

    def _get_or_create_state(self, country, name):
        state, created = State.objects.get_or_create(
            country=country,
            name=name,
            defaults={"slug": slugify(name), "status": "Enabled"},
        )
        if created:
            return state

        updated = False
        if state.slug != slugify(name):
            state.slug = slugify(name)
            updated = True
        if state.status != "Enabled":
            state.status = "Enabled"
            updated = True
        if updated:
            state.save()
        return state

    def _get_or_create_city(self, state, name):
        defaults = {
            "slug": slugify(name),
            "status": "Enabled",
            "internship_text": f"Internships in {name}",
            "meta_title": f"Jobs in {name}",
            "meta_description": f"Discover new opportunities across {name}.",
            "internship_meta_title": f"Internship roles in {name}",
            "internship_meta_description": f"Kickstart careers in {name}.",
            "page_content": f"<p>{name} is part of our demo dataset.</p>",
            "internship_content": f"<p>Internship programs available in {name}.</p>",
            "meta": {},
        }
        city, created = City.objects.get_or_create(
            state=state,
            name=name,
            defaults=defaults,
        )
        if created:
            return city

        updated = False
        for key, value in defaults.items():
            if getattr(city, key) != value:
                setattr(city, key, value)
                updated = True
        if updated:
            city.save()
        return city

    def _get_or_create_city_jobs(
        self,
        *,
        user,
        company,
        industry,
        functional_area,
        qualification,
        skill,
        keyword,
        interview_location,
        country,
        state,
        city,
    ):
        """Ensure at least one live job per city; create up to two for variety."""
        jobs_created = 0
        titles = [
            f"Senior Software Engineer - {city.name}",
            f"Product Specialist - {city.name}",
        ]

        for title in titles:
            slug = slugify(f"{title}-{country.name}")
            job_post = JobPost.objects.filter(slug=slug).first()
            if job_post:
                # keep existing association but ensure location includes city
                job_post.location.add(city)
                continue

            job_post = JobPost(
                user=user,
                code=f"DEMO-{slug[:6].upper()}-{random.randint(1000,9999)}",
                title=title,
                slug=slug,
                job_role="Software Engineer",
                vacancies=random.randint(2, 8),
                country=country,
                description=(
                    f"We are expanding our {city.name} office and looking for talent in {title}."
                ),
                min_year=2,
                min_month=0,
                max_year=8,
                max_month=0,
                fresher=False,
                company=company,
                status="Live",
                previous_status="Live",
                job_type="full-time",
                published_message="Published automatically by seed_sample_geo.",
                company_name=company.name,
                company_address=f"{city.name}, {state.name}, {country.name}",
                company_description=(
                    "Careerlite Demo Company builds scalable platforms and this listing"
                    " was generated for demo purposes."
                ),
                company_links="https://www.careerlite-demo.com",
                company_emails="jobs@careerlite-demo.com",
                meta_title=f"{title} in {city.name}",
                meta_description=(
                    f"Exciting {title.lower()} opportunities now open in {city.name}, "
                    f"{state.name}."
                ),
                min_salary=65000,
                max_salary=110000,
                salary_type="Year",
                last_date=timezone.now().date() + timedelta(days=45),
                published_on=timezone.now(),
                published_date=timezone.now(),
                posted_on=timezone.now(),
                agency_amount="0",
                visa_required=False,
                visa_country=country,
                visa_type="Work Permit",
                major_skill=skill,
            )
            job_post.save()

            job_post.location.set([city])
            job_post.industry.set([industry])
            job_post.functional_area.set([functional_area])
            job_post.skills.set([skill])
            job_post.keywords.set([keyword])
            job_post.edu_qualification.set([qualification])
            job_post.job_interview_location.set([interview_location])
            job_post.agency_recruiters.set([user])

            jobs_created += 1

        return jobs_created

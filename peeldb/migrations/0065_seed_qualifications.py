from django.db import migrations
from django.utils.text import slugify


QUALIFICATIONS_TO_CREATE = [
    ("Bachelor of Computer Science", "Active"),
    ("Master of Data Science", "Active"),
    ("Bachelor of Information Technology", "Active"),
    ("Diploma in Cybersecurity", "Active"),
    ("Certified Cloud Solutions Architect", "Active"),
    ("MBA in Business Analytics", "Active"),
    ("Associate Degree in Software Engineering", "Active"),
    ("Certified Project Management Professional", "Active"),
    ("Bachelor of Mechanical Engineering", "Active"),
    ("Certified Digital Marketing Specialist", "Active"),
    ("Advanced Manufacturing Certification", "Active"),
    ("Certified Data Privacy Professional", "Active"),
    ("Workshop on Creative Writing", "InActive"),
    ("Community Leadership Program", "InActive"),
    ("Weekend Photography Course", "InActive"),
    ("Culinary Arts Masterclass", "InActive"),
    ("Basic Home Repair Training", "InActive"),
    ("Wellness and Mindfulness Retreat", "InActive"),
    ("Travel Blogging Bootcamp", "InActive"),
    ("Gardening for Beginners", "InActive"),
]


def _ensure_unique_slug(model, desired_slug):
    base_slug = desired_slug
    unique_slug = base_slug
    suffix = 1

    while model.objects.filter(slug=unique_slug).exists():
        unique_slug = f"{base_slug}-{suffix}"
        suffix += 1

    return unique_slug


def create_qualifications(apps, schema_editor):
    Qualification = apps.get_model("peeldb", "Qualification")

    for name, status in QUALIFICATIONS_TO_CREATE:
        defaults = {
            "status": status,
        }

        obj, created = Qualification.objects.get_or_create(name=name, defaults=defaults)

        if created:
            obj.slug = _ensure_unique_slug(Qualification, slugify(name) or "qualification")
            obj.save(update_fields=["slug"])
            continue

        updated = False
        if not obj.slug:
            obj.slug = _ensure_unique_slug(Qualification, slugify(name) or "qualification")
            updated = True
        if obj.status != status:
            obj.status = status
            updated = True

        if updated:
            obj.save(update_fields=["slug", "status"])


def remove_qualifications(apps, schema_editor):
    Qualification = apps.get_model("peeldb", "Qualification")
    Qualification.objects.filter(name__in=[name for name, _ in QUALIFICATIONS_TO_CREATE]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("peeldb", "0064_alter_user_managers"),
    ]

    operations = [
        migrations.RunPython(create_qualifications, remove_qualifications),
    ]

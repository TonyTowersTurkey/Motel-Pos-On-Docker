"""Migration to add DynamicPricingRule model.

Adds multi-rate pricing support with seasonal and day-of-week rules.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rooms", "0003_seed_data")]

    operations = [
        migrations.CreateModel(
            name="DayOfWeek",
            fields=[],  # TextChoices doesn't create a separate model
        ),
        migrations.CreateModel(
            name="DynamicPricingRule",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "tier_code",
                    models.CharField(max_length=20),
                ),
                ("name", models.CharField(blank=True, default="", max_length=100)),
                (
                    "rule_type",
                    models.CharField(
                        choices=[
                            ("seasonal", "Seasonal"),
                            ("day_of_week", "Day-of-week"),
                            ("special", "Special date"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "start_date",
                    models.DateField(help_text="Start date of the override window."),
                ),
                (
                    "end_date",
                    models.DateField(
                        blank=True,
                        help_text="Inclusive end date. NULL for open-ended.",
                        null=True,
                    ),
                ),
                (
                    "day_of_week",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("mon", "Monday"),
                            ("tue", "Tuesday"),
                            ("wed", "Wednesday"),
                            ("thu", "Thursday"),
                            ("fri", "Friday"),
                            ("sat", "Saturday"),
                            ("sun", "Sunday"),
                        ],
                        max_length=3,
                    ),
                ),
                (
                    "price_override",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Absolute price override per night.",
                        max_digits=8,
                    ),
                ),
                ("description", models.TextField(blank=True, default="", null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "priority",
                    models.IntegerField(
                        default=100,
                        help_text="Higher priority wins in conflicts.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "dynamic_pricing_rules",
                "ordering": ["-priority"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["tier_code", "rule_type", "day_of_week"],
                        name="unique_tier_day_rule",
                        condition=models.Q(is_active=True),
                        violation_error_message=(
                            "Active rule for this tier/day/type already exists."
                        ),
                    )
                ],
            },
        ),
    ]

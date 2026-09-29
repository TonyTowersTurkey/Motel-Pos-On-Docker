# MVP Design Document: Hotel Room Maintenance & Work Order Management System

## 1. Purpose

Build a Django-based hotel maintenance system to manage room upkeep, ad hoc maintenance requests, planned maintenance schedules, and outstanding work orders.

The system should help hotel staff quickly create maintenance work orders, track unresolved issues, schedule recurring preventive maintenance, and give management visibility into what work needs to be done.

## 2. MVP Goals

The MVP should support:

1. A dashboard showing outstanding work orders.
2. A “work to be done” dashboard for maintenance staff.
3. Ability to create ad hoc work orders.
4. Ability to create planned maintenance tasks.
5. Adjustable room assignment and frequency for planned maintenance.
6. Calendar preview of upcoming planned maintenance.
7. Automatic work order creation from planned maintenance schedules.
8. Basic status tracking and reporting.

## 3. Example Use Cases

### Ad Hoc Maintenance

A cleaning manager enters Room 105 and finds a broken toilet.

The manager opens the system, creates a new maintenance work order:

* Room: 105
* Issue: Broken toilet
* Category: Plumbing
* Priority: High
* Description: Toilet cracked and leaking at base
* Assigned to: Maintenance
* Status: Open

The work order appears immediately on the outstanding work order dashboard and the maintenance work-to-be-done dashboard.

### Planned Maintenance

Management wants air filters cleaned every 6 months.

The system allows creation of a PM rule:

* Task: Clean air filter
* Rooms: All rooms
* Frequency: Every 6 months
* Estimated duration: 20 minutes per room
* Category: HVAC
* Priority: Normal

The system shows a calendar preview before enabling the schedule. Once active, it automatically creates work orders based on the schedule.

## 4. Main Modules

### 4.1 Room Management

Tracks hotel rooms and their maintenance metadata.

Fields:

* Room number
* Building / floor / section
* Room type
* Active / inactive
* Out of service flag
* Notes

Rooms should be selectable when creating both ad hoc and planned maintenance work orders.

### 4.2 Work Order Management

Core module for all maintenance work.

Work orders should include:

* Work order ID
* Room
* Title
* Description
* Category
* Priority
* Status
* Created by
* Assigned to
* Created date
* Due date
* Completed date
* Completion notes
* Source: Ad Hoc or Planned Maintenance

Recommended statuses:

* Open
* Assigned
* In Progress
* Waiting for Parts
* Completed
* Cancelled

Recommended priorities:

* Low
* Normal
* High
* Urgent

### 4.3 Outstanding Work Order Dashboard

This is the management dashboard.

It should show unresolved work orders grouped by:

* Priority
* Room
* Category
* Assigned person
* Age of work order
* Due date

Important dashboard metrics:

* Total open work orders
* Urgent open work orders
* Overdue work orders
* Work orders waiting for parts
* Rooms affected by maintenance
* Average age of open work orders

The dashboard should allow filtering by:

* Room
* Category
* Priority
* Status
* Assigned person
* Date created
* Due date

### 4.4 Work To Be Done Dashboard

This is the operational dashboard for maintenance staff.

It should focus on actionable work.

Default view:

1. Urgent work
2. Overdue work
3. Work due today
4. Assigned work
5. Upcoming planned maintenance

Each item should show:

* Room
* Task title
* Priority
* Due date
* Status
* Assigned person
* Quick action buttons

Quick actions:

* Start work
* Mark waiting for parts
* Complete work
* Add notes

### 4.5 Ad Hoc Work Order Creation

Users should be able to create work orders manually.

Example entry form:

* Room
* Category
* Priority
* Title
* Description
* Optional photo upload
* Assigned to
* Due date
* Notes

Best practice: keep the creation form fast. Cleaning managers and supervisors should be able to create a basic work order in under one minute.

### 4.6 Planned Maintenance Module

Planned maintenance is used for recurring tasks such as:

* Clean air filters every 6 months
* Inspect smoke detectors every 12 months
* Flush water lines every 3 months
* Inspect AC units every 6 months
* Check door locks every 12 months
* Deep clean drains every 3 months

A PM template should include:

* PM name
* Description
* Category
* Default priority
* Frequency
* Rooms included
* Estimated duration
* Start date
* End date, optional
* Active / inactive
* Auto-create work orders setting
* Days before due date to create work order

Frequency options:

* Weekly
* Monthly
* Every 3 months
* Every 6 months
* Yearly
* Custom interval

Room assignment options:

* All rooms
* Selected rooms
* Room group
* Floor
* Building
* Room type

### 4.7 PM Calendar Preview

Before activating a planned maintenance schedule, the user should see a calendar preview.

Calendar preview should show:

* Upcoming PM dates
* Rooms affected
* Number of work orders that will be created
* Estimated labor load per day
* Conflicts with existing maintenance
* Overloaded days

Example:

Clean Air Filter PM
Frequency: Every 6 months
Rooms: 101–120
Preview:

* July 1: Rooms 101–105
* July 2: Rooms 106–110
* July 3: Rooms 111–115
* July 4: Rooms 116–120

The system should support spreading PM work across multiple days instead of creating too many work orders on one day.

## 5. Best Practices for PM-Based Work Order Creation

### 5.1 Do Not Create Too Many Work Orders at Once

For hotel rooms, planned maintenance should usually be batched.

Bad practice:

* Create 100 air filter work orders all due on the same day.

Better practice:

* Create 10–20 work orders per day across one week.

### 5.2 Use Work Order Lead Time

PM templates should define how many days before the due date a work order is created.

Example:

* PM due date: July 15
* Create work order: 7 days before due date
* Work order appears: July 8

This gives maintenance staff time to plan.

### 5.3 Keep PM Templates Separate From Work Orders

A PM template is the rule.

A work order is the actual task created from the rule.

Do not edit old completed work orders when changing a PM schedule. Update the PM template and apply changes only to future work orders.

### 5.4 Avoid Duplicate PM Work Orders

Before generating a PM work order, the system should check whether one already exists for:

* Same PM template
* Same room
* Same due date window

This prevents duplicate work orders.

### 5.5 Use Room Groups

For hotels, room groups make PM scheduling easier.

Examples:

* First floor rooms
* Second floor rooms
* Jacuzzi rooms
* Smoking rooms
* Renovated rooms
* Out-of-service rooms
* Premium rooms

### 5.6 Allow Manual Override

Managers should be able to:

* Skip one occurrence
* Reschedule one occurrence
* Pause a PM schedule
* Change rooms assigned to a PM
* Generate work orders manually from a PM template

### 5.7 Completion Should Record Actual Work

When completing a PM work order, the user should enter:

* Completion notes
* Parts used
* Issues found
* Time spent
* Completed by
* Completion date

This creates a maintenance history per room.

## 6. Django Architecture

## 6.1 Recommended Django Apps

Use separate Django apps for clean organization:

```text
hotel/
  rooms/
  workorders/
  maintenance/
  users/
  dashboard/
  reports/
```

Recommended apps:

### rooms

Handles room records, room groups, and room metadata.

### workorders

Handles ad hoc and generated work orders.

### maintenance

Handles planned maintenance templates, schedules, and PM generation.

### dashboard

Handles dashboard views and summary metrics.

### users

Handles roles and permissions.

### reports

Handles exports, summaries, and future printable reports.

## 6.2 Core Django Models

### Room

```python
class Room(models.Model):
    room_number = models.CharField(max_length=20, unique=True)
    building = models.CharField(max_length=100, blank=True)
    floor = models.CharField(max_length=50, blank=True)
    room_type = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_out_of_service = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
```

### RoomGroup

```python
class RoomGroup(models.Model):
    name = models.CharField(max_length=100)
    rooms = models.ManyToManyField(Room, related_name="groups")
```

### WorkOrder

```python
class WorkOrder(models.Model):
    SOURCE_CHOICES = [
        ("adhoc", "Ad Hoc"),
        ("pm", "Planned Maintenance"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("waiting_parts", "Waiting for Parts"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    room = models.ForeignKey(Room, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="open")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_work_orders",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_work_orders",
    )
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### PlannedMaintenanceTemplate

```python
class PlannedMaintenanceTemplate(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    default_priority = models.CharField(max_length=20, default="normal")
    frequency_months = models.PositiveIntegerField(default=6)
    start_date = models.DateField()
    is_active = models.BooleanField(default=True)
    auto_create_work_orders = models.BooleanField(default=True)
    create_days_before_due = models.PositiveIntegerField(default=7)
    rooms = models.ManyToManyField(Room, blank=True)
    room_groups = models.ManyToManyField(RoomGroup, blank=True)
    estimated_minutes_per_room = models.PositiveIntegerField(default=20)
```

### PlannedMaintenanceOccurrence

```python
class PlannedMaintenanceOccurrence(models.Model):
    template = models.ForeignKey(PlannedMaintenanceTemplate, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.PROTECT)
    due_date = models.DateField()
    work_order = models.OneToOneField(
        WorkOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_skipped = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("template", "room", "due_date")
```

## 7. Views and Pages

## 7.1 Dashboard Pages

### Management Dashboard

URL:

```text
/dashboard/
```

Purpose:

Shows outstanding work orders and maintenance health.

### Work To Be Done Dashboard

URL:

```text
/workorders/todo/
```

Purpose:

Shows actionable work for maintenance staff.

### Work Order List

URL:

```text
/workorders/
```

Purpose:

Search, filter, and view all work orders.

### New Ad Hoc Work Order

URL:

```text
/workorders/new/
```

Purpose:

Create a manual work order quickly.

### PM Templates

URL:

```text
/maintenance/pm/
```

Purpose:

Create and manage planned maintenance templates.

### PM Calendar Preview

URL:

```text
/maintenance/pm/<id>/calendar/
```

Purpose:

Preview future work orders before activation.

## 8. Permissions

Recommended roles:

### Admin

Can manage all rooms, users, PM templates, and work orders.

### Manager

Can create work orders, create PM templates, assign work, and view dashboards.

### Cleaning Manager

Can create ad hoc work orders and view room maintenance status.

### Maintenance Staff

Can view assigned work, update status, add notes, and complete work orders.

### Read Only

Can view dashboards and history.

## 9. Background Jobs

Use Celery or Django-Q for scheduled PM generation.

Recommended MVP approach:

* Use Celery Beat if Redis is already available.
* Use Django management command plus cron if keeping the MVP simple.

Daily job:

```text
generate_pm_work_orders
```

Runs once per day.

Responsibilities:

1. Find active PM templates.
2. Calculate upcoming due dates.
3. Check lead time.
4. Create PM occurrence if missing.
5. Create work order if auto-create is enabled.
6. Avoid duplicates.

## 10. Reporting

MVP reports:

* Open work orders by room
* Open work orders by priority
* Completed work orders by date range
* PM compliance report
* Overdue work orders
* Room maintenance history

Future reports:

* Cost by room
* Parts usage
* Labor time by employee
* Repeat issues by room
* Out-of-service room impact

## 11. MVP Development Phases

### Phase 1: Core Work Orders

Build:

* Room model
* Work order model
* Create work order form
* Work order list
* Outstanding dashboard
* Work-to-be-done dashboard
* Status updates

### Phase 2: Planned Maintenance

Build:

* PM template model
* Room selection
* Frequency selection
* Calendar preview
* Manual PM work order generation

### Phase 3: Automation

Build:

* Daily PM generation job
* Duplicate prevention
* Lead time creation
* Skip/reschedule occurrence

### Phase 4: Reporting

Build:

* Room maintenance history
* Open work order report
* Completed work order report
* PM compliance report

## 12. MVP Success Criteria

The MVP is successful if:

1. Managers can create ad hoc room maintenance work orders.
2. Maintenance staff can see what work needs to be done.
3. Management can see all outstanding work.
4. Planned maintenance can be configured by room and frequency.
5. Upcoming PM work can be previewed on a calendar.
6. PM work orders can be generated without duplicates.
7. Each room has a basic maintenance history.

## 13. Future Enhancements

Possible future features:

* Mobile-first interface for cleaning managers
* Photo uploads
* QR code in each room to create work order
* Parts inventory
* Labor tracking
* Push notifications
* Email or SMS alerts
* Room out-of-service integration
* Motel POS integration
* Guest complaint tracking
* Digital printable maintenance reports
* SMB export for bookkeeping and archive
* AI summary of recurring room issues
* Integration with camera-based occupancy system

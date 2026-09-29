"""Deterministic mock data for the maintenance MVP pages."""

from __future__ import annotations

MAINTENANCE_METRICS = [
    {'label': 'Open Work Orders', 'value': '18', 'tone': 'amber'},
    {'label': 'Urgent', 'value': '4', 'tone': 'red'},
    {'label': 'Overdue', 'value': '6', 'tone': 'orange'},
    {'label': 'Waiting Parts', 'value': '3', 'tone': 'blue'},
    {'label': 'Rooms Affected', 'value': '11', 'tone': 'teal'},
    {'label': 'Avg Age', 'value': '2.4d', 'tone': 'green'},
]

MAINTENANCE_FILTERS = [
    'Room',
    'Category',
    'Priority',
    'Status',
    'Assigned To',
    'Created',
    'Due Date',
]

MAINTENANCE_WORK_ORDERS = [
    {
        'id': 'wo-105',
        'room': '105',
        'title': 'Broken toilet',
        'category': 'Plumbing',
        'priority': 'High',
        'status': 'Open',
        'assigned_to': 'Maintenance',
        'due_date': 'Today',
        'age': '3h',
        'source': 'Ad Hoc',
    },
    {
        'id': 'wo-212',
        'room': '212',
        'title': 'AC filter cleaning',
        'category': 'HVAC',
        'priority': 'Normal',
        'status': 'Assigned',
        'assigned_to': 'Luis',
        'due_date': 'Tomorrow',
        'age': '1d',
        'source': 'Planned',
    },
    {
        'id': 'wo-318',
        'room': '318',
        'title': 'Door lock sticking',
        'category': 'Hardware',
        'priority': 'Urgent',
        'status': 'Waiting for Parts',
        'assigned_to': 'Carla',
        'due_date': 'Overdue',
        'age': '5d',
        'source': 'Ad Hoc',
    },
    {
        'id': 'wo-411',
        'room': '411',
        'title': 'Smoke detector battery test',
        'category': 'Safety',
        'priority': 'Normal',
        'status': 'In Progress',
        'assigned_to': 'Team Lead',
        'due_date': 'Today',
        'age': '7h',
        'source': 'Planned',
    },
    {
        'id': 'wo-208',
        'room': '208',
        'title': 'Replace faucet cartridge',
        'category': 'Plumbing',
        'priority': 'Low',
        'status': 'Open',
        'assigned_to': 'Unassigned',
        'due_date': 'Friday',
        'age': '2d',
        'source': 'Ad Hoc',
    },
]

MAINTENANCE_WORK_QUEUES = [
    {
        'title': 'Urgent Work',
        'subtitle': 'Move these first.',
        'items': [
            {'room': '318', 'task': 'Door lock replacement', 'due': 'Now', 'assigned': 'Carla', 'priority': 'Urgent'},
            {'room': '105', 'task': 'Toilet leak', 'due': 'Now', 'assigned': 'Maintenance', 'priority': 'High'},
        ],
    },
    {
        'title': 'Overdue Work',
        'subtitle': 'Needs immediate attention.',
        'items': [
            {'room': '212', 'task': 'AC drain inspection', 'due': 'Yesterday', 'assigned': 'Luis', 'priority': 'High'},
            {'room': '208', 'task': 'Faucet cartridge replacement', 'due': '2 days ago', 'assigned': 'Unassigned', 'priority': 'Low'},
        ],
    },
    {
        'title': 'Due Today',
        'subtitle': 'Can be completed on this shift.',
        'items': [
            {'room': '411', 'task': 'Smoke detector test', 'due': 'Today', 'assigned': 'Team Lead', 'priority': 'Normal'},
            {'room': '302', 'task': 'Replace shower curtain', 'due': 'Today', 'assigned': 'Maintenance', 'priority': 'Low'},
        ],
    },
    {
        'title': 'Assigned Work',
        'subtitle': 'Already in someone’s hands.',
        'items': [
            {'room': '226', 'task': 'Patch bathroom tile', 'due': 'Friday', 'assigned': 'Luis', 'priority': 'Normal'},
            {'room': '119', 'task': 'Fix loose AC vent', 'due': 'Friday', 'assigned': 'Carla', 'priority': 'Normal'},
        ],
    },
    {
        'title': 'Upcoming PM',
        'subtitle': 'Planned jobs that are about to land.',
        'items': [
            {'room': '101-120', 'task': 'Clean air filters', 'due': 'Next week', 'assigned': 'Team', 'priority': 'Normal'},
            {'room': '201-220', 'task': 'Flush water lines', 'due': 'Next week', 'assigned': 'Team', 'priority': 'High'},
        ],
    },
]

MAINTENANCE_TEMPLATES = [
    {
        'name': 'Clean Air Filters',
        'category': 'HVAC',
        'frequency': 'Every 6 months',
        'rooms': 'All rooms',
        'priority': 'Normal',
        'active': True,
        'next_run': '2026-07-01',
        'est_minutes': 20,
        'spread_days': 4,
    },
    {
        'name': 'Inspect Smoke Detectors',
        'category': 'Safety',
        'frequency': 'Yearly',
        'rooms': 'All rooms',
        'priority': 'High',
        'active': True,
        'next_run': '2026-08-15',
        'est_minutes': 12,
        'spread_days': 3,
    },
    {
        'name': 'Flush Water Lines',
        'category': 'Plumbing',
        'frequency': 'Every 3 months',
        'rooms': 'Selected rooms',
        'priority': 'Urgent',
        'active': False,
        'next_run': '2026-09-01',
        'est_minutes': 30,
        'spread_days': 5,
    },
]

MAINTENANCE_FREQUENCY_OPTIONS = [
    'Weekly',
    'Monthly',
    'Every 3 months',
    'Every 6 months',
    'Yearly',
    'Custom interval',
]

MAINTENANCE_ROOM_ASSIGNMENT_OPTIONS = [
    'All rooms',
    'Selected rooms',
    'Room group',
    'Floor',
    'Building',
    'Room type',
]

MAINTENANCE_PRIORITY_CHOICES = ['Low', 'Normal', 'High', 'Urgent']
MAINTENANCE_CATEGORY_CHOICES = ['Plumbing', 'HVAC', 'Electrical', 'Hardware', 'Housekeeping']
MAINTENANCE_ASSIGNEES = ['Unassigned', 'Maintenance', 'Luis', 'Carla', 'Team Lead']
MAINTENANCE_ROOM_CHOICES = ['101', '102', '105', '119', '208', '212', '226', '302', '318', '411']

MAINTENANCE_PREVIEW_DAYS = [
    {'date': 'July 1', 'rooms': '101-105', 'loads': '100 min', 'conflict': False, 'work_orders': 5},
    {'date': 'July 2', 'rooms': '106-110', 'loads': '100 min', 'conflict': False, 'work_orders': 5},
    {'date': 'July 3', 'rooms': '111-115', 'loads': '120 min', 'conflict': True, 'work_orders': 5},
    {'date': 'July 4', 'rooms': '116-120', 'loads': '100 min', 'conflict': False, 'work_orders': 5},
]

MAINTENANCE_ROOMS = [
    {'room': '101', 'building': 'A', 'floor': '1', 'type': 'Queen', 'active': True, 'out': False, 'group': 'North Wing'},
    {'room': '102', 'building': 'A', 'floor': '1', 'type': 'Queen', 'active': True, 'out': False, 'group': 'North Wing'},
    {'room': '119', 'building': 'A', 'floor': '1', 'type': 'King', 'active': True, 'out': False, 'group': 'South Wing'},
    {'room': '208', 'building': 'B', 'floor': '2', 'type': 'Queen', 'active': True, 'out': False, 'group': 'East Wing'},
    {'room': '212', 'building': 'B', 'floor': '2', 'type': 'King', 'active': True, 'out': False, 'group': 'East Wing'},
    {'room': '226', 'building': 'B', 'floor': '2', 'type': 'Double', 'active': True, 'out': False, 'group': 'West Wing'},
    {'room': '302', 'building': 'C', 'floor': '3', 'type': 'Queen', 'active': True, 'out': False, 'group': 'Pool Side'},
    {'room': '318', 'building': 'C', 'floor': '3', 'type': 'Double', 'active': True, 'out': True, 'group': 'Pool Side'},
    {'room': '411', 'building': 'D', 'floor': '4', 'type': 'King', 'active': False, 'out': True, 'group': 'Annex'},
]


MAINTENANCE_DIALOG_RECORDS = [
    {
        'id': 'wo-105',
        'room': '105',
        'title': 'Broken toilet',
        'category': 'Plumbing',
        'priority': 'High',
        'status': 'Open',
        'source': 'Ad Hoc',
        'assigned_to': 'Maintenance',
        'created_by': 'Ana',
        'created_at': '2026-06-21 08:12',
        'due_date': '2026-06-21',
        'completed_at': '',
        'description': 'Toilet cracked and leaking at base. Shut off valve is available behind the fixture. Toilet cracked and leaking at base.',
        'instructions': 'Bring wax ring, supply line, and replacement toilet bolts. Shut off water before removing.',
        'issues_found': 'Cracked porcelain bowl; minor floor water damage.',
        'parts_used': 'Wax ring, toilet bolts, supply line',
        'completion_notes': 'Replace fixture and verify no leaks after flush test.',
        'time_spent_minutes': 0,
        'estimated_minutes': 45,
        'location_notes': 'Room is in the south hallway; use manager key for entry.',
        'safety_notes': 'Use wet-floor sign if water is present.',
        'attachments': ['photo_105_before.jpg', 'room_105_floor.jpg'],
        'checklist': [
            'Confirm room access',
            'Shut off water',
            'Replace failed part',
            'Test flush twice',
            'Document cleanup',
        ],
    },
    {
        'id': 'wo-318',
        'room': '318',
        'title': 'Door lock sticking',
        'category': 'Hardware',
        'priority': 'Urgent',
        'status': 'Waiting for Parts',
        'source': 'Ad Hoc',
        'assigned_to': 'Carla',
        'created_by': 'Jose',
        'created_at': '2026-06-20 19:44',
        'due_date': '2026-06-21',
        'completed_at': '',
        'description': 'Guest reported key card needs several attempts and deadbolt drags when closing.',
        'instructions': 'Inspect latch alignment, replace strike plate if necessary, and test with master key.',
        'issues_found': 'Latch scrape visible; replacement strike plate requested.',
        'parts_used': 'Strike plate on order',
        'completion_notes': 'Once parts arrive, retest lock cycle 10 times before closing.',
        'time_spent_minutes': 15,
        'estimated_minutes': 30,
        'location_notes': 'Room is on the third floor near the stairwell.',
        'safety_notes': 'No special safety concerns.',
        'attachments': ['lock_closeup.jpg'],
        'checklist': [
            'Verify symptom',
            'Inspect strike plate',
            'Test latch and deadbolt',
            'Order parts if needed',
            'Log follow-up visit',
        ],
    },
    {
        'id': 'wo-411',
        'room': '411',
        'title': 'Smoke detector battery test',
        'category': 'Safety',
        'priority': 'Normal',
        'status': 'In Progress',
        'source': 'Planned',
        'assigned_to': 'Team Lead',
        'created_by': 'System',
        'created_at': '2026-06-21 06:00',
        'due_date': '2026-06-21',
        'completed_at': '',
        'description': 'Planned monthly safety check for detector response and battery condition.',
        'instructions': 'Press test button, confirm audible alert, and replace battery if weak.',
        'issues_found': '',
        'parts_used': '',
        'completion_notes': 'Record the detector serial number and note any missing units.',
        'time_spent_minutes': 20,
        'estimated_minutes': 15,
        'location_notes': 'Annex building, fourth floor.',
        'safety_notes': 'Use ladder only if required; have a second person present.',
        'attachments': [],
        'checklist': [
            'Check detector status',
            'Press test button',
            'Replace battery if needed',
            'Record results',
            'Complete maintenance note',
        ],
    },
]


MAINTENANCE_WORK_ORDERS = MAINTENANCE_DIALOG_RECORDS

# Box Management Server

A Flask REST API server for managing boxes and users with TinyDB as the local database.

## Features

- Add and delete boxes
- Update box attributes (box_number, port_number)
- Assign users to boxes (one-to-one relationship)
- Assign users to any free box
- Unassign users from boxes
- Get all free boxes
- Get all boxes
- Get box assigned to a specific user

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python app.py
```

The server will start on `http://0.0.0.0:5000`

## Database

The database is stored in `boxes.json` (auto-created on first run). Each box document contains:
- `box_id`: Auto-generated unique integer ID
- `box_number`: String box number (provided when creating box)
- `port_number`: String port number
- `user_id`: Integer user ID or `null` if the box is free

## API Endpoints

### 1. Add Box
**POST** `/boxes`

Request body:
```json
{
  "box_number": "BOX-001",
  "port_number": "8080"
}
```

Response (201):
```json
{
  "box_id": 1,
  "box_number": "BOX-001",
  "port_number": "8080",
  "user_id": null
}
```

### 2. Delete Box
**DELETE** `/boxes/<box_id>`

Response (200):
```json
{
  "message": "Box deleted successfully"
}
```

### 3. Assign User to Box
**POST** `/boxes/assign`

Request body (with specific box):
```json
{
  "user_id": 123,
  "box_id": 1
}
```

Request body (auto-assign to any free box):
```json
{
  "user_id": 123
}
```

Response (200):
```json
{
  "box_id": 1,
  "box_number": "BOX-001",
  "user_id": 123,
  "port_number": "8080"
}
```

Note: If the user already has a box assigned, the old box will be automatically unassigned.

### 4. Assign User to Free Box
**POST** `/boxes/assign_user_to_free_box`

Request body:
```json
{
  "user_id": 123
}
```

Response (200):
```json
{
  "box_id": 1,
  "box_number": "BOX-001",
  "user_id": 123,
  "port_number": "8080"
}
```

Note: This endpoint specifically assigns a user to any available free box. If the user already has a box assigned, the old box will be automatically unassigned. If no free boxes are available, returns a 404 error.

### 5. Unassign User from Box
**POST** `/boxes/unassign`

Request body (by user_id):
```json
{
  "user_id": 123
}
```

Request body (by box_id):
```json
{
  "box_id": 1
}
```

Response (200):
```json
{
  "message": "User unassigned from box successfully"
}
```

### 6. Get Free Boxes
**GET** `/boxes/free`

Response (200):
```json
[
  {
    "box_id": 1,
    "box_number": "BOX-001",
    "port_number": "8080",
    "user_id": null
  },
  {
    "box_id": 3,
    "box_number": "BOX-003",
    "port_number": "8082",
    "user_id": null
  }
]
```

### 7. Get All Boxes
**GET** `/boxes`

Response (200):
```json
[
  {
    "box_id": 1,
    "box_number": "BOX-001",
    "port_number": "8080",
    "user_id": null
  },
  {
    "box_id": 2,
    "box_number": "BOX-002",
    "port_number": "8081",
    "user_id": 456
  }
]
```

### 8. Get Box by User ID
**GET** `/boxes/user/<user_id>`

Response (200) - User has a box:
```json
{
  "has_box": true,
  "box_id": 1,
  "box_number": "BOX-001",
  "user_id": "123",
  "port_number": "8080"
}
```

Response (200) - User has no box:
```json
{
  "has_box": false
}
```

### 9. Update Box
**PUT** or **PATCH** `/boxes/<box_id>`

Request body (update one or both fields):
```json
{
  "box_number": "BOX-001-UPDATED",
  "port_number": "8081"
}
```

Response (200):
```json
{
  "box_id": 1,
  "box_number": "BOX-001-UPDATED",
  "port_number": "8081",
  "user_id": null
}
```

Note: You can update `box_number` and/or `port_number`. At least one field must be provided. The `box_id` and `user_id` cannot be updated through this endpoint.

## Error Responses

All endpoints return appropriate HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad Request (validation errors)
- `404`: Not Found

Error response format:
```json
{
  "error": "Error message"
}
```


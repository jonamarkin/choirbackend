# SMS & Contact Groups - Frontend Integration Guide

## Overview

This guide covers integrating the SMS sending and contact management features into your frontend application.

---

## Authentication

All endpoints require JWT authentication:

```typescript
headers: {
  'Authorization': 'Bearer <access_token>',
  'Content-Type': 'application/json'
}
```

---

## API Endpoints Summary

### SMS Endpoints

| Method | Endpoint                                | Description                     |
| ------ | --------------------------------------- | ------------------------------- |
| POST   | `/api/v1/communication/sms/send-single` | Send SMS to one recipient       |
| POST   | `/api/v1/communication/sms/send-batch`  | Send SMS to multiple recipients |

### Contact Groups

| Method | Endpoint                                                    | Description             |
| ------ | ----------------------------------------------------------- | ----------------------- |
| GET    | `/api/v1/communication/contact-groups`                      | List all groups         |
| POST   | `/api/v1/communication/contact-groups`                      | Create group            |
| GET    | `/api/v1/communication/contact-groups/{id}`                 | Get group with contacts |
| PUT    | `/api/v1/communication/contact-groups/{id}`                 | Update group            |
| DELETE | `/api/v1/communication/contact-groups/{id}`                 | Delete group            |
| POST   | `/api/v1/communication/contact-groups/{id}/add-contacts`    | Add contacts to group   |
| POST   | `/api/v1/communication/contact-groups/{id}/remove-contacts` | Remove from group       |
| GET    | `/api/v1/communication/contact-groups/{id}/contacts`        | List group contacts     |

### Contacts

| Method | Endpoint                                     | Description          |
| ------ | -------------------------------------------- | -------------------- |
| GET    | `/api/v1/communication/contacts`             | List all contacts    |
| POST   | `/api/v1/communication/contacts`             | Create contact       |
| POST   | `/api/v1/communication/contacts/bulk-create` | Bulk create contacts |
| PUT    | `/api/v1/communication/contacts/{id}`        | Update contact       |
| DELETE | `/api/v1/communication/contacts/{id}`        | Delete contact       |

### Members (for SMS)

| Method | Endpoint                                              | Description              |
| ------ | ----------------------------------------------------- | ------------------------ |
| GET    | `/api/v1/communication/members/phones`                | List members with phones |
| GET    | `/api/v1/communication/members/phones/by-part/{part}` | Filter by voice part     |
| GET    | `/api/v1/communication/members/phones/by-role/{role}` | Filter by role           |

---

## TypeScript Interfaces

```typescript
// SMS Types
interface SingleSMSRequest {
  to: string; // Phone number e.g., "233209335976"
  content: string; // Message content
}

interface SingleSMSResponse {
  rate: number;
  messageId: string;
  status: number;
  networkId: string | null;
  clientReference: string | null;
  statusDescription: string;
}

interface BatchSMSRequest {
  recipients: string[]; // Array of phone numbers
  content: string;
}

interface BatchRecipient {
  recipient: string;
  content: string;
  messageId: string;
}

interface BatchSMSResponse {
  batchId: string;
  status: number;
  data: BatchRecipient[];
}

// Contact Types
interface Contact {
  id: string;
  name: string;
  phone_number: string;
  groups: string[]; // Array of group IDs
  user_id?: string; // Optional linked user
  created_at: string;
  updated_at: string;
}

interface ContactGroup {
  id: string;
  name: string;
  description: string;
  contact_count: number;
  created_at: string;
  updated_at: string;
}

interface ContactGroupDetail extends ContactGroup {
  contacts: Contact[];
}

// Member Types
interface MemberPhone {
  id: string;
  full_name: string;
  phone_number: string;
  email: string;
  member_part: string;
  role: string;
}
```

---

## Example API Calls

### Send Single SMS

```typescript
const sendSingleSMS = async (to: string, content: string) => {
  const response = await fetch("/api/v1/communication/sms/send-single", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ to, content }),
  });
  return response.json();
};
```

### Send Batch SMS

```typescript
const sendBatchSMS = async (recipients: string[], content: string) => {
  const response = await fetch("/api/v1/communication/sms/send-batch", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ recipients, content }),
  });
  return response.json();
};
```

### Send SMS to Contact Group

```typescript
const sendSMSToGroup = async (groupId: string, content: string) => {
  // 1. Fetch group contacts
  const contactsRes = await fetch(
    `/api/v1/communication/contact-groups/${groupId}/contacts`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  const contacts: Contact[] = await contactsRes.json();

  // 2. Extract phone numbers
  const recipients = contacts.map((c) => c.phone_number);

  // 3. Send batch SMS
  return sendBatchSMS(recipients, content);
};
```

### Bulk Create Contacts with Group

```typescript
const bulkCreateContacts = async (
  contacts: { name: string; phone_number: string }[],
  groupId?: string,
) => {
  const response = await fetch("/api/v1/communication/contacts/bulk-create", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ contacts, group_id: groupId }),
  });
  return response.json();
};
```

---

## UI/UX Recommendations

### SMS Compose Page Structure

```
┌─────────────────────────────────────────────────┐
│ Send SMS                                        │
├─────────────────────────────────────────────────┤
│ Recipients:                                     │
│ ┌─────────────────────────────────────────────┐ │
│ │ [Tab: Manual] [Tab: Contacts] [Tab: Groups] │ │
│ │ [Tab: Members]                              │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ Selected: 12 recipients                         │
│ ┌─────────────────────────────────────────────┐ │
│ │ [Chip] John Doe  [x]                        │ │
│ │ [Chip] Jane Doe  [x]                        │ │
│ │ [Chip] +2 more...                           │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ Message:                                        │
│ ┌─────────────────────────────────────────────┐ │
│ │                                             │ │
│ │ Enter your message here...                  │ │
│ │                                             │ │
│ └─────────────────────────────────────────────┘ │
│ Characters: 45/160 (1 SMS)                      │
│                                                 │
│              [Preview] [Send SMS]               │
└─────────────────────────────────────────────────┘
```

### Suggested Components

1. **SMSComposer** - Main compose form
2. **RecipientSelector** - Tabbed selector for different sources
3. **ContactPicker** - Searchable list with checkboxes
4. **GroupPicker** - Select entire groups
5. **MemberPicker** - Filter by part/role
6. **RecipientChips** - Display selected recipients
7. **CharacterCounter** - Track SMS length

### Key UX Features

- **Multi-select** - Allow selecting from contacts, groups, AND members simultaneously
- **De-duplication** - Auto-remove duplicate phone numbers before sending
- **Search/Filter** - Search contacts by name, filter members by part
- **Character count** - Show SMS count (160 chars = 1 SMS)
- **Preview** - Show message preview before sending
- **Confirmation** - Confirm before sending to large groups

---

## Voice Part Values

For filtering members by voice part:

- `soprano`, `alto`, `tenor`, `bass`, `instrumentalist`, `directorate`

## Role Values

For filtering members by role:

- `super_admin`, `admin`, `finance_admin`, `attendance_officer`, `treasurer`, `part_leader`, `member`

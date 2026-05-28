````md
# 📌 [08 - USER STORY] — Secure Platform (Access, Registration, and Profile Management)

> ✍️ **Author:** Paloma Soares &nbsp;|&nbsp; 🗓️ **Edited:** May 04 &nbsp;|&nbsp; 🔖 **Version:** 3.0 &nbsp;|&nbsp; 🟢 **Status:** `Ready`

---

## 🎯 1. Overview

This feature ensures that the platform remains a secure and restricted environment, accessible exclusively to authenticated Tecsys consultants, while providing full autonomy for account creation, access, and credential management.

- **Objective:** Protect the platform’s strategic commercial data and allow each consultant to independently manage their own access without relying on technical support or IT assistance.
- **Problem:** Without authentication, anyone with the platform link would have unrestricted access to utility company reports, criticality indexes, and loss analysis data that support active commercial proposals. Additionally, without self-service account management, every new consultant registration or password reset would require manual IT intervention.
- **KPI / Success:** Only consultants with a Tecsys corporate email address can create accounts and access the platform. Once authenticated, consultants have full control over their credentials.

---

## 🎨 2. Visual Behavior

### 🔗 Prototype Link (Figma)

> _Not applicable_

```text
Consultant accesses the platform
        ↓
Login Screen
  ├── [First Access] → "Create Account" → Fill in Name, Corporate Email, and Password
  └── [Returning Users] → Fill in Email and Password → Click "Sign In"
        ↓
After authentication → Dashboard with full access
        ↓
Menu → "My Profile" → Update Name or Password
````

---

## 📋 3. Narrative

**As** a Tecsys sales consultant,
**I want** exclusive and secure access to the platform using my corporate credentials,
**So that** only authenticated team members can view strategic reports and analyses, and I can manage my account independently without relying on technical support.

---

### Happy Path

#### Registration

1. The consultant accesses "Create Account" and fills in their Name, Tecsys corporate email, and Password.
2. The system validates the email domain in real time.
3. The backend hashes the password (bcrypt/Argon2) and stores it in PostgreSQL.
4. A JWT is automatically generated, and the consultant is redirected to the Dashboard without needing to log in again.

#### Login

1. The consultant enters their Email and Password on the Login screen.
2. The backend validates the password hash in PostgreSQL and returns a JWT with expiration.
3. The consultant is redirected to the Dashboard with full access.
4. When clicking "Logout," the token is removed and the consultant returns to the Login screen.

#### Profile Management

1. The authenticated consultant accesses "My Profile" through the menu.
2. They can view their Name and Email (email is read-only).
3. They update their Name and/or New Password by providing the Current Password.
4. The system confirms: *"Profile updated successfully!"*

---

## 🛡️ 4. Business Rules

* **Data Source:** PostgreSQL relational database — exclusively dedicated to account management.
* **Corporate Domain:** Only email addresses from the Tecsys domain are accepted.
* **Passwords:** Must never be stored in plain text. Always use secure hashing (bcrypt or Argon2).
* **Immutable Email:** The consultant’s unique identifier — cannot be changed after registration.
* **Security Through Obscurity:** Login error messages must not reveal whether the issue is the email or the password.
* **Dependency:** This User Story is a prerequisite for all others — all API routes (FastAPI) must be configured as protected routes, granting access only through a valid JWT token.

---

## ✅ 5. Acceptance Criteria

### Registration

| Step           | Action|
| -------------- | ---------------- |
| **Given that** | the consultant is on the "Create Account" screen|
| **When**       | they enter their Name, a valid Tecsys domain email, and a password that meets the minimum requirements, then click "Register" |
| **Then**       | the system must register the consultant, generate a JWT, and automatically redirect them to the Dashboard|

| Step           | Action                                                                                           |
| -------------- | ------------------------------------------------------------------------------------------------ |
| **Given that** | the consultant is filling out the registration form                                              |
| **When**       | they enter an email outside the corporate domain or an email already registered                  |
| **Then**       | the system must block the registration and display a clear, specific error message for each case |

---

### Login

| Step           | Action|
| -------------- | -----------------|
| **Given that** | the consultant is on the Login screen with an existing account|
| **When**       | they enter the correct email and password and click "Sign In"|
| **Then**       | the API must validate the password hash, return a JWT, and redirect the consultant to the Dashboard |

| Step           | Action|
| -------------- | -----------------|
| **Given that** | someone attempts to access a private route without a valid JWT token|
| **When**       | the backend receives the request|
| **Then**       | the API must return HTTP 401, and the frontend must redirect the user to the Login screen without displaying any data |

---

### Profile Management

| Step           | Action|
| -------------- | ----------------- |
| **Given that** | the consultant is on the "My Profile" screen|
| **When**       | they update their Name and/or correctly provide the Current Password and New Password, then click "Save" |
| **Then**       | the system must update the data in the database and display a success confirmation|

---

## 🏁 6. Definition of Done (DoD)

#### Registration

* [ ] "Create Account" screen implemented with real-time domain and password requirement validation
* [ ] Password stored using secure hashing (bcrypt or Argon2)
* [ ] JWT generated and session automatically started after registration
* [ ] Blocking of invalid domain emails and duplicate emails with clear error messages

#### Login

* [ ] Login screen implemented with standardized error messages (without revealing which field is incorrect)
* [ ] FastAPI authentication route validating password hashes and returning JWTs with expiration
* [ ] All private routes protected, returning HTTP 401 for requests without a valid token
* [ ] Manual logout implemented with token removal on the frontend

#### Profile Management

* [ ] "My Profile" screen with fields for Name, Email (read-only), Current Password, and New Password
* [ ] Current Password validation through backend hash comparison before any update
* [ ] New Password stored using secure hashing
* [ ] Success and error messages fully functional in the interface


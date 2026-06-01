# Trendit API — Detailed Reference

**Base URL:** `https://<your-domain>/api/`
**Version:** Built from source — verified against all views, serializers, and models.

---

## Table of Contents

1. [Global Response Format](#1-global-response-format)
2. [Authentication Overview](#2-authentication-overview)
3. [User Authentication & Management](#3-user-authentication--management)
   - [POST /users/register/](#31-register-user)
   - [POST /users/verify-otp/](#32-verify-otp)
   - [POST /users/login/](#33-login-obtain-jwt-tokens)
   - [POST /users/token/refresh/](#34-refresh-access-token)
   - [POST /users/forgot-password/](#35-request-forgot-password-otp)
   - [POST /users/reset-password/](#36-reset-password-with-otp)
   - [POST /users/violations/](#37-record-user-violation--strike)
4. [Profile & Search](#4-profile--search)
   - [GET/PATCH /users/profile/](#41-get--update-own-profile)
   - [GET /users/search/](#42-search-users)
   - [GET /users/profile/<user_id>/](#43-view-other-user-profile)
5. [Admin — User Banning](#5-admin--user-banning)
   - [POST /users/ban/<user_id>/](#51-ban-a-user)
   - [POST /users/unban/<user_id>/](#52-unban-a-user)
6. [Content — Posts](#6-content--posts)
   - [POST /content/upload-signature/](#61-get-cloudinary-upload-signature)
   - [POST /content/posts/](#62-create-post)
   - [GET /content/posts/<id>/](#63-get-post-detail)
   - [PATCH /content/posts/<id>/](#64-update-post-partial)
   - [DELETE /content/posts/<id>/](#65-delete-post)
   - [GET /content/feed/](#66-get-post-feed)
   - [GET /content/trending/](#67-get-trending-feed)
   - [GET /content/posts/user/<user_id>/](#68-get-posts-by-user)
   - [POST /content/subposts/](#69-create-sub-post)
   - [GET /content/categories/](#610-list-categories)
7. [Social — Follow System](#7-social--follow-system)
   - [POST /social/follow/](#71-follow-a-user)
   - [DELETE /social/follow/](#72-unfollow-a-user)
   - [GET /social/following/ (or /following/<user_id>/)](#73-list-users-followed)
   - [GET /social/followers/ (or /followers/<user_id>/)](#74-list-users-followers)
8. [Social — Buddy System](#8-social--buddy-system)
   - [GET /social/buddies/](#81-list-mutual-buddies)
9. [Social — Close Buddy (Inner Circle)](#9-social--close-buddy-inner-circle)
   - [POST /social/close-buddies/request/](#91-send-close-buddy-request)
   - [POST /social/close-buddies/respond/](#92-respond-to-close-buddy-request)
   - [GET /social/close-buddies/requests/](#93-list-incoming-close-buddy-requests)
   - [GET /social/close-buddies/pending-sent/](#94-list-pending-sent-close-buddy-requests)
   - [GET /social/close-buddies/](#95-list-your-inner-circle)
   - [GET /social/close-buddies/added-by/](#910-list-users-who-added-you-to-their-inner-circle)
   - [GET /social/close-buddies/suggestions/](#911-list-close-buddy-suggestions)
   - [DELETE /social/close-buddies/remove/](#96-remove-someone-from-inner-circle)
   - [GET /social/close-buddies/unapproved-posts/](#97-list-unapproved-posts-from-your-close-buddies)
   - [GET /social/close-buddies/requests/rejected/](#98-list-rejected-close-buddy-requests)
   - [GET /social/close-buddies/requests/ignored/](#99-list-ignored-close-buddy-requests)
10. [Social — Interactions](#10-social--interactions)
    - [POST /social/approve-post/](#101-approve-a-post)
    - [POST /social/vote/](#102-vote-on-a-post)
    - [POST /social/favorite/](#103-toggle-favorite-on-a-post)
11. [Core — Notifications](#11-core--notifications)
    - [GET /core/notifications/](#111-list-notifications)
    - [PATCH /core/notifications/<id>/read/](#112-mark-notification-as-read)
12. [Core — Reports](#12-core--reports)
    - [POST /core/report/](#121-submit-a-report)
13. [Core — Media Cleanup (Cron)](#13-core--media-cleanup-cron)
    - [POST /core/cleanup-media/](#131-cleanup-expired-media)
14. [Shared Object Schemas](#14-shared-object-schemas)

---

## 1. Global Response Format

Every response from the API goes through two layers of formatting.

### 1a. Success Responses (HTTP 2xx)

Handled by `StandardizedJSONRenderer`. Every 2xx response is wrapped as:

```json
{
  "status": "success",
  "code": 200,
  "message": "Action completed successfully.",
  "data": { ... }
}
```

- The `"message"` value is the default `"Action completed successfully."` **unless** the view explicitly included a `"message"` key in its response dictionary, in which case that custom message is lifted to the top level and removed from `"data"`.
- List endpoints return `"data"` as an array of objects.
- Some endpoints (e.g., mark notification as read) return `"data"` as a small dict like `{"status": "notification marked as read"}`.

### 1b. Error Responses (HTTP 4xx / 5xx)

Handled by `custom_exception_handler`. All errors are wrapped as:

```json
{
  "status": "error",
  "code": 401,
  "message": "Human-readable error description.",
  "errors": { ... }
}
```

- `"errors"` is the raw DRF validation error dict (field-level errors) for `400 Bad Request` responses; `null` for all other error codes.
- The `"message"` is auto-generated by status code unless the exception carries a `"detail"` or `"non_field_errors"` value, which is then used directly.
- For `400` errors, if there is no `"detail"`, the first field error is used as the message (e.g., `"email: user with this email address already exists."`).

**Common HTTP Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 400 | Bad Request (validation failure) |
| 401 | Unauthorized (no/expired/invalid token, or blocked login) |
| 403 | Forbidden (authenticated but not permitted) |
| 404 | Not Found |
| 500 | Internal Server Error (e.g., Cloudinary connectivity) |

---

## 2. Authentication Overview

- **Method:** JWT (JSON Web Tokens) via `rest_framework_simplejwt`.
- **Header:** `Authorization: Bearer <access_token>`
- The `access` token must be included in the `Authorization` header for all protected endpoints.
- **Login flexibility:** The login endpoint accepts **username**, **email**, or **phone number** in the `username` field. This is handled by `DualLoginBackend` + `CustomTokenObtainPairSerializer`.

---

## 3. User Authentication & Management

### 3.1 Register User

**`POST /api/users/register/`**

Creates a new user account. The account is **not active** until the email OTP is verified. Automatically generates a username from the email (e.g., `john@example.com` → `john`; if taken, tries `john1`, `john2`, etc.).

**Authentication Required:** No

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | Must be a valid email address. Unique among verified users. |
| `password` | string | ✅ Yes | User's password. Will be hashed. |
| `phone_number` | string | ❌ No | E.164 format (e.g., `+923001234567`). Unique among verified users. |

**Success Response — `201 Created`:**

```json
{
  "status": "success",
  "code": 201,
  "message": "User registered successfully. Please verify your email with the OTP sent.",
  "data": {
    "email": "john@example.com"
  }
}
```

> Note: Only `email` is returned in `data`. A 6-digit OTP is emailed to the user. The OTP expires in **10 minutes**.

**Error Responses:**

| Condition | Status | `errors` field |
|-----------|--------|----------------|
| `email` missing or invalid format | 400 | `{"email": ["Enter a valid email address."]}` |
| Verified user already exists with this email | 400 | `{"email": ["user with this email address already exists."]}` |
| Verified user already exists with this phone number | 400 | `{"phone_number": ["user with this phone number already exists."]}` |
| `password` missing | 400 | `{"password": ["This field is required."]}` |

**Edge Cases:**

- If an **unverified** user already exists with the same `email` or `phone_number`, that old unverified account is **silently deleted** and a fresh registration is created. This allows users to retry registration cleanly.
- `id` is **not** included in the response — only `email`.
- Phone number is stored as `None` (not `""`) if not provided or left blank, to avoid unique constraint issues.

---

### 3.2 Verify OTP

**`POST /api/users/verify-otp/`**

Verifies the OTP sent to the user's email during registration (or any other OTP flow). Marks the user as verified (`is_verified = true`) and deletes the used OTP.

**Authentication Required:** No

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | Can be the user's **email**, **username**, or **phone number**. |
| `otp_code` | string (6 chars) | ✅ Yes | The 6-digit code received via email. |

> Despite the field name being `email`, the system accepts email, username, or phone number as the identifier. The field name is a legacy naming from the serializer.

**Success Response — `200 OK`:**

```json
{
  "status": "success",
  "code": 200,
  "message": "Account verified successfully. You can now login.",
  "data": {}
}
```

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| User not found for the given identifier | 400 | "Please check your input and try again." |
| OTP does not match, is expired, or has been used | 400 | "Please check your input and try again." |
| `email` or `otp_code` missing | 400 | Validation error for the missing field |

**Edge Cases:**

- The OTP is matched against the **latest** valid (non-expired) OTP for the user.
- OTP expiry: 10 minutes from creation.
- Upon success, the OTP record is deleted from the database.
- If a user somehow has multiple OTPs (e.g., re-registered), the system uses `.latest('created_at')` to pick the most recent one.

---

### 3.3 Login (Obtain JWT Tokens)

**`POST /api/users/login/`**

Authenticates a user and returns a JWT access/refresh token pair. The `username` field is a **unified identifier** that accepts email, username, or phone number.

**Authentication Required:** No

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | ✅ Yes | User's **email**, **username**, or **phone number**. |
| `password` | string | ✅ Yes | User's password. |

**Success Response — `200 OK`:**

```json
{
  "status": "success",
  "code": 200,
  "message": "Action completed successfully.",
  "data": {
    "refresh": "<JWT refresh token>",
    "access": "<JWT access token>",
    "user_id": 42
  }
}
```

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| Wrong credentials (user not found or wrong password) | 401 | "No active account found with the given credentials." |
| Account exists but is **not verified** | 401 | "ACCOUNT_NOT_VERIFIED" |
| Account is **banned** | 401 | "Your account has been banned. Reason: \<ban_reason\>" |
| Missing `username` or `password` | 400 | Field-level validation error |

**Edge Cases:**

- If the account is **unverified**, a **fresh OTP is generated and emailed** before the 401 is returned. The client should redirect the user to the OTP verification screen.
- If the account is **banned**, the specific ban reason is included in the `message`. The `code` on the error body will be `not_verified` or `account_banned` respectively (these are simplejwt error codes accessible in the raw exception, but are not guaranteed to surface in the standardized response `message`).
- `user_id` is always included in the success response for the client to cache.

---

### 3.4 Refresh Access Token

**`POST /api/users/token/refresh/`**

Exchanges a valid refresh token for a new access token.

**Authentication Required:** No (uses the refresh token itself)

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh` | string | ✅ Yes | A valid, non-expired JWT refresh token. |

**Success Response — `200 OK`:**

```json
{
  "status": "success",
  "code": 200,
  "message": "Action completed successfully.",
  "data": {
    "access": "<new JWT access token>"
  }
}
```

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| Refresh token is expired or invalid | 401 | "Your session has expired or you are not logged in." |
| `refresh` field missing | 400 | Field-level validation error |

---

### 3.5 Request Forgot Password OTP

**`POST /api/users/forgot-password/`**

Sends a password-reset OTP to the user's email address. Invalidates all previous OTPs for that user before creating a new one.

**Authentication Required:** No

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | The email address associated with the account. |

**Success Response — `200 OK`:**

```json
{
  "status": "success",
  "code": 200,
  "message": "Password reset OTP sent to email.",
  "data": {
    "email": "john@example.com"
  }
}
```

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| No account with this email exists | 400 | "email: Account with this email does not exist." |
| Invalid email format | 400 | Field-level validation error |

**Edge Cases:**

- All existing OTPs for this user are deleted before the new one is created.
- The new OTP expires in **10 minutes**.
- This endpoint does **not** reveal whether an email is registered if the email is not found — wait, actually it **does** return a `400` error if the email doesn't exist. Clients should handle this gracefully.

---

### 3.6 Reset Password with OTP

**`POST /api/users/reset-password/`**

Verifies the password-reset OTP and sets the new password.

**Authentication Required:** No

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | The account's email address. |
| `otp_code` | string (6 chars) | ✅ Yes | The OTP received via the forgot-password email. |
| `new_password` | string | ✅ Yes | The new password. Minimum length: **6 characters**. |

**Success Response — `200 OK`:**

```json
{
  "status": "success",
  "code": 200,
  "message": "Password has been reset successfully. You can now login.",
  "data": {}
}
```

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| User not found or OTP invalid/expired | 400 | "Please check your input and try again." |
| `new_password` shorter than 6 characters | 400 | Field-level validation error |
| Any field missing | 400 | Field-level validation error |

**Edge Cases:**

- On success, the OTP is deleted from the database.
- The password is properly hashed via Django's `set_password()`.
- After reset, the user must log in again (no tokens are returned).

---

### 3.7 Record User Violation / Strike

**`POST /api/users/violations/`**

Records a user violation (strike) sent from the client application. If the user's total violations reach 3 or more, they are automatically banned and a reason is saved in their profile.

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `rule_broken` | string | ❌ No | The rule that was broken (default: `"Client Rule Broken"`). |
| `description` | string | ❌ No | Additional context about the violation. |

**Success Response — `201 Created` (`data` object):**

```json
{
  "status": "success",
  "code": 201,
  "message": "Violation recorded. Warning shown. You have 2 remaining violation(s) before your account is banned.",
  "data": {
    "total_violations": 1,
    "remaining_violations": 2,
    "is_banned": false
  }
}
```

If the violation causes the user to be banned (e.g., reaching 3 violations):

```json
{
  "status": "success",
  "code": 201,
  "message": "Your account has been banned due to exceeding the maximum violation limit of 3.",
  "data": {
    "total_violations": 3,
    "remaining_violations": 0,
    "is_banned": true
  }
}
```

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| Not authenticated | 401 | "Your session has expired or you are not logged in." |

**Edge Cases:**

- Banned users cannot log in (login will return `401 Unauthorized` with `account_banned` detail).
- If the user is already banned, subsequent violations will still be recorded and return `is_banned: true` and `remaining_violations: 0`.

---

## 4. Profile & Search

### 4.1 Get / Update Own Profile

**`GET /api/users/profile/`**
**`PUT /api/users/profile/`**
**`PATCH /api/users/profile/`**

Returns or updates the **currently authenticated user's** profile information.

**Authentication Required:** Yes

**GET — Success Response `200 OK` (`data` object):**

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | User's primary key. Read-only. |
| `username` | string | Editable. |
| `email` | string | Read-only (cannot be changed through this endpoint). |
| `phone_number` | string \| null | E.164 format. Editable. |
| `first_name` | string | Editable. |
| `last_name` | string | Editable. |
| `profile_picture` | string \| null | URL to the uploaded image or `null`. Editable. |

**PUT/PATCH Request Body (multipart/form-data or JSON):**

| Field | Type | Required for PUT | Required for PATCH | Description |
|-------|------|------------------|--------------------|-------------|
| `username` | string | ✅ Yes | ❌ No | New username. Must be unique. |
| `phone_number` | string | ❌ No | ❌ No | E.164 format. |
| `first_name` | string | ❌ No | ❌ No | |
| `last_name` | string | ❌ No | ❌ No | |
| `profile_picture` | file | ❌ No | ❌ No | Image file upload. Use `multipart/form-data`. |

> `id` and `email` are **always read-only** and will be ignored if sent in the request body.

**Error Responses:**

| Condition | Status | Notes |
|-----------|--------|-------|
| Not authenticated | 401 | |
| Username already taken by another user | 400 | |

---

### 4.2 Search Users

**`GET /api/users/search/?q=<query>`**

Searches users by `username`, `first_name`, or `last_name`. Also accessible at `/api/social/users/search/` (same view mounted at two URLs).

**Authentication Required:** Yes

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | string | ✅ Yes | Search query. Case-insensitive partial match on `username`, `first_name`, `last_name`. |

**Success Response — `200 OK` (`data` is an array):**

Each object in the array:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | User ID. |
| `username` | string | |
| `email` | string | |
| `first_name` | string | |
| `last_name` | string | |
| `profile_picture` | string \| null | URL of the profile picture, or `null`. |
| `is_following` | boolean | `true` if the authenticated user follows this user. |
| `is_followed_by` | boolean | `true` if this user follows the authenticated user. |
| `is_buddy` | boolean | `true` if they are mutual buddies. |
| `is_close_buddy` | boolean | `true` if this user is in the authenticated user's inner circle. |
| `close_buddy_request_status` | string \| null | Close buddy request status between them. Format: `sent_<status>` (e.g. `sent_pending`, `sent_accepted`, `sent_rejected`, `sent_ignored`) or `received_<status>` (e.g. `received_pending`, `received_accepted`, `received_rejected`, `received_ignored`) or `null` if no request exists. |

**Edge Cases:**

- Returns an **empty list** (`[]`) if `q` is absent or blank.
- Excludes the **requesting user** from results.
- Only returns **active** users (`is_active=True`).
- Maximum **30 results** are returned.
- Ordering: alphabetical by `username`.

---

### 4.3 View other User Profile

**`GET /api/users/profile/<int:user_id>/`**

Retrieves detailed profile information for a specific user, including followers/following/buddy counts and relationship statuses with the authenticated user.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` object):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Target user ID. |
| `username` | string | |
| `first_name` | string | |
| `last_name` | string | |
| `profile_picture` | string \| null | URL to the user's profile picture or `null`. |
| `followers_count` | int | Count of followers of the user. |
| `following_count` | int | Count of users the user is following. |
| `buddies_count` | int | Count of mutual buddies of the user. |
| `total_posts` | int | Total number of published posts by the user. |
| `is_following` | boolean | `true` if the authenticated user follows this user. |
| `is_followed_by` | boolean | `true` if this user follows the authenticated user. |
| `is_buddy` | boolean | `true` if they are mutual buddies. |
| `is_close_buddy` | boolean | `true` if this user is in the authenticated user's inner circle. |
| `close_buddy_request_status` | string \| null | Close buddy request status if any exists between them. Format: `sent_pending`, `received_pending`, `sent_accepted`, etc. or `null`. |

---

## 5. Admin — User Banning

Both endpoints require the authenticated user to be a **staff/admin** (`is_staff=True`). Returns `403 Forbidden` for non-admin users.

### 5.1 Ban a User

**`POST /api/users/ban/<user_id>/`**

Bans a user account. Banned users cannot log in.

**Authentication Required:** Yes (Admin only)

**URL Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `user_id` | int | Primary key of the user to ban. |

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ban_reason` | string | ❌ No | Optional reason for the ban. Stored on the user record. |

**Success Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| User successfully banned | 200 | "User '\<username\>' has been banned." |
| User was already banned | 200 | "User '\<username\>' is already banned." |

**`data` object on success:**

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | (lifted to top-level by renderer) |
| `ban_reason` | string | The ban reason stored, or `"No reason provided."` if empty. |

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| `user_id` not found | 404 | "The item you are looking for was not found." |
| Target user is a superuser | 403 | "Superusers cannot be banned." |
| Requester is not admin | 403 | "You do not have permission to perform this action." |

---

### 5.2 Unban a User

**`POST /api/users/unban/<user_id>/`**

Removes a ban from a user.

**Authentication Required:** Yes (Admin only)

**URL Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `user_id` | int | Primary key of the user to unban. |

**Request Body:** None required.

**Success Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| User successfully unbanned | 200 | "User '\<username\>' has been unbanned." |
| User was not banned | 200 | "User '\<username\>' is not banned." |

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| `user_id` not found | 404 | "The item you are looking for was not found." |
| Requester is not admin | 403 | "You do not have permission to perform this action." |

---

## 6. Content — Posts

### Shared: Post Object Schema

This schema is used in all endpoints that return post data (feed, trending, detail, user posts, vote/favorite responses).

| Field | Type | Writable? | Description |
|-------|------|-----------|-------------|
| `id` | int | No | Post primary key. |
| `author` | int | No | User ID of the post author. |
| `author_username` | string | No | Username of the author. |
| `author_profile_picture` | string \| null | No | URL to the author's profile picture, or `null`. |
| `category` | int \| null | Yes | Category ID. |
| `category_name` | string \| null | No | Name of the category. |
| `media_file` | string \| null | Yes | Cloudinary public URL of the media. `null` if media was deleted. |
| `caption` | string | Yes | Post caption text. |
| `aspect_ratio` | float \| null | Yes | e.g., `1.7778` for 16:9. Client-provided metadata. |
| `duration` | float \| null | Yes | Video duration in seconds. Client-provided. Max 60. |
| `size` | int \| null | Yes | File size in bytes. Client-provided. Max 62,914,560 (60 MB). |
| `status` | string | No | One of: `"pending"`, `"active"`, `"trending"`, `"rejected"`. |
| `created_at` | string | No | ISO 8601 datetime. |
| `is_media_deleted` | bool | No | `true` if media has been purged from Cloudinary (after 7 days). |
| `avg_rating` | float \| null | No | Annotated. Average of all votes (1–5). `null` if no votes. |
| `vote_count` | int | No | Annotated. Total number of votes. |
| `user_rating` | int \| null | No | Annotated. The requesting user's own vote (1–5), or `null`. `null` for anonymous users. |
| `favorite_count` | int | No | Annotated. Total number of times the post was favorited. |
| `is_favorited` | bool | No | Annotated. `true` if the requesting user has favorited this post. `false` for anonymous users. |
| `sub_posts` | array | No | Array of SubPost objects (see below). |

#### SubPost Object Schema

Nested inside `sub_posts` on every Post object.

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | SubPost primary key. |
| `parent_post` | int | ID of the parent Post. |
| `author` | int | User ID. |
| `author_username` | string | |
| `author_profile_picture` | string \| null | URL or `null`. |
| `media_file` | string \| null | Cloudinary URL or `null`. |
| `caption` | string | Can be empty. |
| `aspect_ratio` | float \| null | |
| `duration` | float \| null | |
| `size` | int \| null | |
| `created_at` | string | ISO 8601 datetime. |

---

### 6.1 Get Cloudinary Upload Signature

**`POST /api/content/upload-signature/`**

Generates a signed parameter set for **direct client-to-Cloudinary** uploads. The client uses these credentials to upload media directly to Cloudinary without routing the file through the Django server.

**Authentication Required:** Yes

**Request Body:** None (no body required).

**Success Response — `200 OK` (`data` object):**

| Field | Type | Description |
|-------|------|-------------|
| `signature` | string | HMAC signature for the upload request. |
| `timestamp` | int | Unix timestamp at time of signing. |
| `api_key` | string | Cloudinary API key. |
| `cloud_name` | string | Cloudinary cloud name. |
| `folder` | string | Always `"posts"`. The folder where media will be uploaded in Cloudinary. |

**Client Workflow:**

1. Call this endpoint to get the signature.
2. Use the returned values to make a POST request directly to `https://api.cloudinary.com/v1_1/<cloud_name>/auto/upload` with the file and these params.
3. Cloudinary responds with the uploaded file's `public_id` and `secure_url`.
4. Include `media_file` = the Cloudinary `public_id` (or URL) when calling `POST /api/content/posts/`.

---

### 6.2 Create Post

**`POST /api/content/posts/`**

Creates a new post. The post starts in `"pending"` status and must be approved by the author's close buddies before becoming `"active"`.

**Authentication Required:** Yes

**Request Body (JSON or multipart/form-data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | int | ✅ Yes | ID of an existing Category. |
| `caption` | string | ✅ Yes | Post caption text. |
| `media_file` | string | ❌ No | The Cloudinary public_id or URL of the already-uploaded media. |
| `aspect_ratio` | float | ❌ No | Aspect ratio (e.g., `1.7778`). Client-provided metadata. |
| `duration` | float | ❌ No | Video duration in seconds. Must be ≤ 60. |
| `size` | int | ❌ No | File size in bytes. Must be ≤ 62,914,560 (60 MB). |

> `author` and `status` are **automatically set** by the server. `author` = requesting user; `status` = `"pending"`.

**Success Response — `201 Created` (`data` = full Post Object):**

Returns the full Post object (see [Post Object Schema](#shared-post-object-schema)).

**Error Responses:**

| Condition | Status | Notes |
|-----------|--------|-------|
| Not authenticated | 401 | |
| Invalid/missing `category` | 400 | |
| `duration` > 60 seconds | 400 | `"Video duration must be 60 seconds or less."` |
| `size` > 60 MB | 400 | `"Media file is too large. Videos must be 60MB or less."` |
| Upload outside allowed window | 400 | `"Uploads are only allowed between <start> and <end>."` (enforced by `AppSettings`) |
| `caption` missing | 400 | |

**Edge Cases:**

- If no `AppSettings` record exists in the database, the upload time window check is **skipped**.
- The `status` is always `"pending"` on creation. It becomes `"active"` automatically after all of the author's close buddies approve it (see [Approve a Post](#101-approve-a-post)).
- If the author has **zero close buddies**, posts will never auto-activate through the approval flow — they stay `"pending"` indefinitely unless changed by an admin.

---

### 6.3 Get Post Detail

**`GET /api/content/posts/<id>/`**

Retrieves the full detail of a single post.

**Authentication Required:** No (but `user_rating` and `is_favorited` will be `null`/`false` for anonymous users)

**URL Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `id` | int | Post primary key. |

**Success Response — `200 OK` (`data` = full Post Object):**

Returns the full Post object (see [Post Object Schema](#shared-post-object-schema)) including all annotations and nested `sub_posts`.

**Error Responses:**

| Condition | Status | Notes |
|-----------|--------|-------|
| Post not found | 404 | |

---

### 6.4 Update Post (Partial)

**`PATCH /api/content/posts/<id>/`**

Partially updates a post. Only the **post author** can perform updates.

**Authentication Required:** Yes (must be the author)

**URL Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `id` | int | Post primary key. |

**Request Body (JSON — all fields optional):**

| Field | Type | Description |
|-------|------|-------------|
| `caption` | string | New caption. |
| `category` | int | New category ID. |
| `aspect_ratio` | float | New aspect ratio. |
| `duration` | float | New duration (must still be ≤ 60). |
| `size` | int | New size (must still be ≤ 60 MB). |

> `author`, `status`, and `created_at` are read-only and cannot be changed.

**Success Response — `200 OK` (`data` = full updated Post Object)**

**Error Responses:**

| Condition | Status | Notes |
|-----------|--------|-------|
| Not authenticated | 401 | |
| Authenticated but not the author | 403 | |
| Post not found | 404 | |

---

### 6.5 Delete Post

**`DELETE /api/content/posts/<id>/`**

Deletes a post. Only the **post author** can delete. Also deletes the associated media from Cloudinary.

**Authentication Required:** Yes (must be the author)

**URL Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `id` | int | Post primary key. |

**Success Response — `204 No Content`**

No body is returned.

**Error Responses:**

| Condition | Status | Notes |
|-----------|--------|-------|
| Not authenticated | 401 | |
| Authenticated but not the author | 403 | |
| Post not found | 404 | |

**Edge Cases:**

- Cloudinary deletion is attempted first. If the Cloudinary API call fails, the error is **silently ignored** and the database record is still deleted.
- This permanently deletes the Post DB record and all related SubPosts (cascade), votes, favorites, and approvals.

---

### 6.6 Get Post Feed

**`GET /api/content/feed/`**

Returns all posts where media has not been deleted, ordered newest first.

**Authentication Required:** No (anonymous access allowed; user-specific annotations will be null/false)

**Success Response — `200 OK` (`data` is an array of Post Objects)**

All posts where `is_media_deleted=False`, ordered by `-created_at` (newest first).

**Notes:**

- This feed includes posts of **all statuses** (pending, active, trending, rejected). The client is responsible for filtering by status if needed.
- Includes user-specific annotation (`user_rating`, `is_favorited`) if authenticated.

---

### 6.7 Get Trending Feed

**`GET /api/content/trending/`**

Returns the top 10 trending posts, ranked by rating and vote count.

**Authentication Required:** No (anonymous access allowed)

**Success Response — `200 OK` (`data` is an array of up to 10 Post Objects)**

Filters: `status` is `"active"` or `"trending"`, `is_media_deleted=False`.
Ordering: `-avg_rating`, then `-vote_count`, then `-created_at`.

**Notes:**

- At most **10 posts** are returned.
- Only publicly visible (active/trending) posts appear here.

---

### 6.8 Get Posts by User

**`GET /api/content/posts/user/<user_id>/`**

Returns all posts by a specific user.

**Authentication Required:** No (read access is public; but visibility of statuses depends on identity)

**URL Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `user_id` | int | The user whose posts to retrieve. |

**Visibility Rules:**

| Requester | Posts Shown |
|-----------|-------------|
| The post's own author (authenticated, same `user_id`) | All statuses: pending, active, trending, rejected |
| Anyone else (anonymous or different user) | Only `active` and `trending` posts |

**Success Response — `200 OK` (`data` is an array of Post Objects)**

Ordered by `-created_at` (newest first). Posts with deleted media **are included** (unlike the feed).

---

### 6.9 Create Sub-Post

**`POST /api/content/subposts/`**

Creates a media-based reply (sub-post) to an existing post.

**Authentication Required:** Yes

**Request Body (JSON or multipart/form-data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `parent_post` | int | ✅ Yes | ID of the Post this is a reply to. |
| `media_file` | string | ❌ No | Cloudinary public_id or URL of the uploaded media. |
| `caption` | string | ❌ No | Caption text (can be empty). |
| `aspect_ratio` | float | ❌ No | Client-provided metadata. |
| `duration` | float | ❌ No | Duration in seconds. Must be ≤ 60. |
| `size` | int | ❌ No | Size in bytes. Must be ≤ 60 MB. |

> `author` is automatically set to the requesting user. `created_at` is set by the server.

**Success Response — `201 Created` (`data` = SubPost Object):**

Returns the full SubPost object (see [SubPost Object Schema](#subpost-object-schema)).

**Error Responses:**

| Condition | Status | Notes |
|-----------|--------|-------|
| Not authenticated | 401 | |
| `parent_post` does not exist | 400 | |
| `duration` > 60 | 400 | |
| `size` > 60 MB | 400 | |
| Upload outside allowed time window | 400 | Enforced by `AppSettings` |

---

### 6.10 List Categories

**`GET /api/content/categories/`**

Returns all available post categories.

**Authentication Required:** No

**Success Response — `200 OK` (`data` is an array):**

Each object:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Category primary key. |
| `name` | string | Category display name (e.g., `"Music"`, `"Dance"`). |
| `slug` | string | URL-safe version of the name (e.g., `"music"`, `"dance"`). Auto-generated. |

---

## 7. Social — Follow System

### 7.1 Follow a User

**`POST /api/social/follow/`**

Follows a target user. No permission needed from the target. If both users follow each other, a **Buddy** relationship is automatically created (via signal).

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | int | ✅ Yes | ID of the user to follow. |

**Success Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| Successfully followed | 201 | "You are now following \<username\>." |
| Already following this user | 200 | "You are already following \<username\>." |

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| `user_id` missing | 400 | "user_id is required." |
| `user_id` not found | 404 | "The item you are looking for was not found." |
| Trying to follow yourself | 400 | "You cannot follow yourself." |

**Side Effect:**

- If the target user is **already following** the requester, a `Buddy` record is automatically created (mutual follow → buddy).

---

### 7.2 Unfollow a User

**`DELETE /api/social/follow/`**

Unfollows a target user. If a Buddy relationship existed, it is **automatically removed** (via signal).

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | int | ✅ Yes | ID of the user to unfollow. |

**Success Response — `200 OK`:**

`"message": "You have unfollowed <username>."`

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| `user_id` missing | 400 | "user_id is required." |
| `user_id` not found | 404 | "The item you are looking for was not found." |
| Not currently following this user | 404 | "You are not following this user." |

**Side Effect:**

- If a `Buddy` record existed between these two users, it is **automatically deleted**.

---

### 7.3 List Users Followed

**`GET /api/social/following/`**
**`GET /api/social/following/<int:user_id>/`**

Returns the list of users followed by the **authenticated user** (if no `user_id` is supplied) or by the user specified by `user_id`.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of UserMinimal objects):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | User ID. |
| `username` | string | |
| `email` | string | |
| `first_name` | string | |
| `last_name` | string | |
| `profile_picture` | string \| null | URL of the profile picture, or `null`. |

Ordered alphabetically by `username`.

---

### 7.4 List Users' Followers

**`GET /api/social/followers/`**
**`GET /api/social/followers/<int:user_id>/`**

Returns the list of users who are following the **authenticated user** (if no `user_id` is supplied) or the user specified by `user_id`.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of UserMinimal objects)**

Same schema as [7.3](#73-list-users-followed). Ordered alphabetically by `username`.

---

## 8. Social — Buddy System

Buddies are **automatically managed** — they are created when two users follow each other (via signals) and deleted when either unfollows. There is no manual buddy creation endpoint.

### 8.1 List Mutual Buddies

**`GET /api/social/buddies/`**

Returns all users who are mutual buddies with the authenticated user (i.e., both follow each other).

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of UserMinimal objects)**

Same schema as [7.3](#73-list-users-you-follow). Ordered alphabetically by `username`.

---

## 9. Social — Close Buddy (Inner Circle)

Close Buddies are a privileged group of up to **5** users whose approval is needed for a post to go live. The flow:

1. User A sends a request to User B (`POST /social/close-buddies/request/`) — **only works if they are mutual buddies**.
2. User B accepts (`POST /social/close-buddies/respond/` with `action: "accepted"`).
3. A `CloseBuddy` record is created: User A's inner circle now includes User B.

### 9.1 Send Close Buddy Request

**`POST /api/social/close-buddies/request/`**

Sends a request to add a mutual buddy to your inner circle.

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `receiver` | int | ✅ Yes | User ID of the person you want in your inner circle. |

**Success Response — `201 Created` (`data` = CloseBuddyRequest object):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Request ID. |
| `sender` | int | Sender's user ID. |
| `receiver` | int | Receiver's user ID. |
| `sender_details` | object | `{id, username, email, first_name, last_name}` |
| `receiver_details` | object | `{id, username, email, first_name, last_name}` |
| `status` | string | Always `"pending"` on creation. |
| `created_at` | string | ISO 8601 datetime. |

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| Not a mutual buddy with receiver | 400 | "You can only send close buddy requests to mutual buddies." |
| Sending request to yourself | 400 | "You cannot send a close buddy request to yourself." |
| A pending request to this user already exists | 400 | "You already have a pending request to this user." |
| Receiver is already in your inner circle | 400 | "This user is already in your inner circle." |
| Your inner circle already has 5 close buddies | 400 | "Your inner circle is full (max 5 close buddies)." |

---

### 9.2 Respond to Close Buddy Request

**`POST /api/social/close-buddies/respond/`**

Accepts or rejects an incoming close buddy request. Only the **receiver** of the request can respond.

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | int | ✅ Yes | ID of the `CloseBuddyRequest` to respond to. |
| `action` | string | ✅ Yes | One of: `"accepted"`, `"rejected"`, or `"ignored"`. |

**Success Response — `200 OK`:**

`"message": "Close buddy request accepted."`, `"Close buddy request rejected."`, or `"Close buddy request ignored."`

`"data"` is `{}`.

**On Acceptance:**

A `CloseBuddy` record is created: `user = sender`, `buddy = receiver (current user)`. This means the sender now has the receiver in *their* inner circle.

**On Rejection or Ignore:**

The request's `status` is updated to `"rejected"` or `"ignored"` respectively, and no close buddy relationship is created.

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| `request_id` not found, or already processed, or receiver is not current user | 404 | "The item you are looking for was not found." |
| Sender's inner circle already full (5 close buddies) at time of acceptance | 400 | "Sender's inner circle is already full (max 5)." |
| `action` is not `"accepted"`, `"rejected"`, or `"ignored"` | 400 | Field validation error |

---

### 9.3 List Incoming Close Buddy Requests

**`GET /api/social/close-buddies/requests/`**

Returns all **pending** close buddy requests sent **to** the authenticated user.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of CloseBuddyRequest objects)**

Each object has the same schema as [9.1](#91-send-close-buddy-request). Ordered by `-created_at` (newest first).

---

### 9.4 List Pending Sent Close Buddy Requests

**`GET /api/social/close-buddies/pending-sent/`**

Returns all close buddy requests the authenticated user **sent** that are still pending.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of CloseBuddyRequest objects)**

Same schema as [9.1](#91-send-close-buddy-request). Ordered by `-created_at` (newest first).

---

### 9.5 List Your Inner Circle

**`GET /api/social/close-buddies/`**

Returns the authenticated user's current inner circle (close buddies).

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array):**

Each object:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | CloseBuddy record ID. |
| `buddy` | int | User ID of the close buddy. |
| `buddy_details` | object | `{id, username, email, first_name, last_name}` |

Maximum of 5 items.

---

### 9.6 Remove Someone from Inner Circle

**`DELETE /api/social/close-buddies/remove/`**

Removes a user from the authenticated user's inner circle.

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | int | ✅ Yes | User ID of the person to remove from inner circle. |

**Success Response — `200 OK`:**

`"message": "User removed from your inner circle."`

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| `user_id` missing | 400 | "user_id is required." |
| User not in your inner circle | 404 | "This user is not in your inner circle." |

---

### 9.7 List Unapproved Posts from Your Close Buddies

**`GET /api/social/close-buddies/unapproved-posts/`**

Returns posts from your inner circle members that are still `"pending"` and that **you have not yet approved**.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of Post Objects)**

Filters applied:
- `author` must be one of the authenticated user's close buddies (i.e., in `CloseBuddy` where `user = current_user`).
- Post `status` must be `"pending"`.
- `is_media_deleted` must be `False`.
- The current user must **not** have already approved the post.

Ordered by `-created_at` (newest first).

---

### 9.8 List Rejected Close Buddy Requests

**`GET /api/social/close-buddies/requests/rejected/`**

Returns all close buddy requests sent **to** the authenticated user that have been **rejected**.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of CloseBuddyRequest objects)**

Each object has the same schema as [9.1](#91-send-close-buddy-request). Ordered by `-created_at` (newest first).

---

### 9.9 List Ignored Close Buddy Requests

**`GET /api/social/close-buddies/requests/ignored/`**

Returns all close buddy requests sent **to** the authenticated user that have been **ignored**.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of CloseBuddyRequest objects)**

Each object has the same schema as [9.1](#91-send-close-buddy-request). Ordered by `-created_at` (newest first).

---

### 9.10 List Users Who Added You to Their Inner Circle

**`GET /api/social/close-buddies/added-by/`**

Returns all users who have added the authenticated user to their inner circle.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array):**

Each object:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | CloseBuddy record ID. |
| `user` | int | User ID of the person who added you. |
| `user_details` | object | [Minimal User Object](#141-minimal-user-object). |

---

### 9.11 List Close Buddy Suggestions

**`GET /api/social/close-buddies/suggestions/`**

Returns a list of mutual buddies who are not yet in your inner circle and don't have pending close buddy requests.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array of User Search objects):**

Each object follows the [User Search Object Schema](#142-user-search-object).

---

## 10. Social — Interactions

### 10.1 Approve a Post

**`POST /api/social/approve-post/`**

Approves a pending post. Only **close buddies of the post's author** can approve. When all close buddies have approved, the post status changes to `"active"` automatically.

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `post` | int | ✅ Yes | ID of the post to approve. |

**Success Response — `201 Created` (`data` = PostApproval object):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Approval record ID. |
| `post` | int | Post ID. |
| `buddy` | int | User ID of the approving buddy (current user). |
| `approved_at` | string | ISO 8601 datetime. |

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| Current user is not a close buddy of the post's author | 400 | "Only close buddies of the author can approve this post." |
| Post is not in `"pending"` status | 400 | "This post is not pending approval." |
| Already approved this post (unique constraint) | 400 | Field validation error |

**Auto-Activation Logic:**

After each approval, the system checks: `total_approvals >= total_close_buddies_of_author`. If true, `post.status` is set to `"active"`.

> Note: There is also a signal (`check_post_approval_count`) that independently sets `status = "active"` when `approval_count >= 3`. Both mechanisms run — the view logic uses the **exact count of close buddies**, while the signal uses a hardcoded threshold of **3**. In practice, the view logic takes effect first.

---

### 10.2 Vote on a Post

**`POST /api/social/vote/`**

Records a rating for a post on a 1–5 scale. If the user has **already voted**, the existing vote is **updated** to the new value (upsert behavior).

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `post` | int | ✅ Yes | ID of the post to vote on. |
| `value` | int | ✅ Yes | Rating value. Must be an integer from **1 to 5** (inclusive). |

**Success Response — `201 Created`:**

Returns the **full updated Post Object** (all annotations recalculated), plus:

```json
{
  "status": "success",
  "code": 201,
  "message": "Vote recorded successfully.",
  "data": {
    "id": 7,
    "author": 3,
    "author_username": "jane",
    ...
    "avg_rating": 4.2,
    "vote_count": 10,
    "user_rating": 5,
    "favorite_count": 3,
    "is_favorited": false,
    "sub_posts": [...]
  }
}
```

The full Post Object (including recalculated `avg_rating`, `vote_count`, and the new `user_rating`) is returned so the client can **immediately sync UI state** without a separate GET request.

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| `value` not in range 1–5 | 400 | Field validation error |
| `post` not found | 400 | |
| Not authenticated | 401 | |

---

### 10.3 Toggle Favorite on a Post

**`POST /api/social/favorite/`**

Toggles a post as a favorite. If already favorited, removes it. If not favorited, adds it.

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `post` | int | ✅ Yes | ID of the post to toggle. |

**Success Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| Post was not favorited → now favorited | 201 | "Added to favorites." |
| Post was favorited → now unfavorited | 200 | "Removed from favorites." |

In both cases, `"data"` is the **full updated Post Object** with recalculated `favorite_count` and updated `is_favorited` value.

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| `post` field missing in body | 400 | "post ID is required." |
| Post not found | 404 | "The item you are looking for was not found." |
| Not authenticated | 401 | |

---

## 11. Core — Notifications

### 11.1 List Notifications

**`GET /api/core/notifications/`**

Returns all notifications for the authenticated user, ordered newest first.

**Authentication Required:** Yes

**Success Response — `200 OK` (`data` is an array):**

Each notification object:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Notification primary key. |
| `recipient` | int | User ID of the recipient (always the current user). |
| `actor` | int | User ID of the user who triggered the action. |
| `actor_username` | string | Username of the actor. |
| `verb` | string | Short description of the action (e.g., `"rated your post"`). |
| `target` | object \| null | The related object (Post, SubPost, etc.) if it still exists. This is a GenericForeignKey. |
| `read_status` | bool | `false` if unread, `true` if read. |
| `created_at` | string | ISO 8601 datetime. |

---

### 11.2 Mark Notification as Read

**`PATCH /api/core/notifications/<id>/read/`**

Marks a specific notification as read.

**Authentication Required:** Yes

**URL Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `id` | int | Notification primary key. |

**Request Body:** None required.

**Success Response — `200 OK`:**

```json
{
  "status": "success",
  "code": 200,
  "message": "Action completed successfully.",
  "data": {
    "status": "notification marked as read"
  }
}
```

**Error Responses:**

| Condition | Status | Notes |
|-----------|--------|-------|
| Notification not found | 404 | |
| Notification belongs to another user | 403 | Returns empty 403 (no body — raw `403` status). |

---

## 12. Core — Reports

### 12.1 Submit a Report

**`POST /api/core/report/`**

Submits a report against any content object (e.g., a Post). Uses Django's generic foreign key to link to any model.

**Authentication Required:** Yes

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content_type` | int | ✅ Yes | The ID of the `ContentType` record for the model being reported (e.g., the ContentType ID for `Post`). |
| `object_id` | int | ✅ Yes | The primary key of the specific object being reported (e.g., the Post ID). |
| `reason` | string | ✅ Yes | Reason for the report. Free text. |

> `reporter` is automatically set to the requesting user. `status` defaults to `"submitted"`. `created_at` is set by the server.

**How to get `content_type` ID:** Query `/admin/contenttypes/contenttype/` or make a pre-flight call to find the correct ContentType ID for `Post` (typically `app_label="content"`, `model="post"`). This ID is stable per deployment.

**Success Response — `201 Created` (`data` object):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Report primary key. |
| `reporter` | int | Reporting user's ID. |
| `content_type` | int | ContentType ID. |
| `object_id` | int | Reported object's ID. |
| `reason` | string | Report reason. |
| `status` | string | Always `"submitted"` on creation. |
| `created_at` | string | ISO 8601 datetime. |

**Error Responses:**

| Condition | Status | Notes |
|-----------|--------|-------|
| Not authenticated | 401 | |
| `content_type`, `object_id`, or `reason` missing | 400 | Field validation error |

---

## 13. Core — Media Cleanup (Cron)

### 13.1 Cleanup Expired Media

**`POST /api/core/cleanup-media/`**

Deletes Cloudinary media files for posts and sub-posts older than **7 days**. Designed to be called by an external cron job (e.g., cron-job.org) once per day. The database records are **preserved** — only the media files are deleted from Cloudinary and `is_media_deleted` is set to `true`.

**Authentication Required:** Custom secret token (not JWT)

**Authorization Header:**

```
Authorization: Bearer <CLEANUP_SECRET_TOKEN>
```

The `CLEANUP_SECRET_TOKEN` is a server-side environment variable. JWT authentication is bypassed for this endpoint.

**Request Body:** None.

**Success Response — `200 OK` (`data` object):**

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | `"Cleanup complete"` (lifted to top-level message). |
| `posts_cleaned` | int | Number of Post media files successfully deleted from Cloudinary. |
| `subposts_cleaned` | int | Number of SubPost media files successfully deleted from Cloudinary. |

**Error Responses:**

| Condition | Status | `message` |
|-----------|--------|-----------|
| Wrong or missing `Authorization` header | 403 | "Forbidden" |

**Cleanup Logic:**

- Finds all Posts where `created_at < (now - 7 days)` AND `is_media_deleted=False` AND `media_file` is not empty.
- For each, calls Cloudinary's destroy API, then sets `media_file = null` and `is_media_deleted = true`.
- Same logic for SubPosts.
- If a Cloudinary deletion fails, that record is **skipped** (not counted in `posts_cleaned`).

---

## 14. Shared Object Schemas

### UserMinimal Object

Returned by follow/buddy/search endpoints.

| Field | Type |
|-------|------|
| `id` | int |
| `username` | string |
| `email` | string |
| `first_name` | string |
| `last_name` | string |

### CloseBuddyRequest Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | |
| `sender` | int | User ID of the request sender. |
| `receiver` | int | User ID of the request receiver. |
| `sender_details` | UserMinimal object | |
| `receiver_details` | UserMinimal object | |
| `status` | string | `"pending"`, `"accepted"`, or `"rejected"`. |
| `created_at` | string | ISO 8601 datetime. |

### Post Status Lifecycle

```
[Created] → "pending" → (all close buddies approve) → "active"
                      → (admin action) → "rejected"
"active"  → (admin action) → "trending"
```

- Posts start as `"pending"`.
- They become `"active"` when all of the author's close buddies have approved, OR when 3 approvals exist (signal-based fallback).
- `"trending"` status is set by admin through the Django admin panel.
- `"rejected"` is set by admin.
- **Anonymous users** and non-author users can only see `"active"` and `"trending"` posts in feed/user-post endpoints.

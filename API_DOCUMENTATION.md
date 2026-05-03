# Trendit API Documentation

This document provides a comprehensive detail of each endpoint provided by the Trendit backend project.

## Table of Contents
1. [User Authentication & Management](#1-user-authentication--management)
2. [Content Management (Posts & Categories)](#2-content-management-posts--categories)
3. [Social Interactions (Buddies & Voting)](#3-social-interactions-buddies--voting)
4. [Core Features (Notifications & Reporting)](#4-core-features-notifications--reporting)

---

## 1. User Authentication & Management

### Register User
*   **URL:** `/api/users/register/`
*   **Method:** `POST`
*   **Description:** Registers a new user account using email and password. A unique username is automatically generated from the email prefix. A 6-digit OTP is generated and printed to the console for verification.
*   **Input Data (JSON):**
    *   `email` (string, required)
    *   `password` (string, required)
*   **Success Response:**
    *   **Status Code:** `201 Created`
    *   **Data:** `{"message": "User registered successfully. Please verify your email with the OTP sent.", "email": "user@example.com"}`
*   **Failure Response:**
    *   **Status Code:** `400 Bad Request`
    *   **Reason:** Validation error (e.g., email already exists, missing fields).

### Verify OTP
*   **URL:** `/api/users/verify-otp/`
*   **Method:** `POST`
*   **Description:** Verifies the user's email using the OTP sent during registration.
*   **Input Data (JSON):**
    *   `email` (string, required)
    *   `otp_code` (string, 6 characters, required)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"message": "Email verified successfully. You can now login."}`
*   **Failure Response:**
    *   **Status Code:** `400 Bad Request`
    *   **Reason:** Invalid or expired OTP, or user not found.

### Login (Obtain Token)
*   **URL:** `/api/users/login/`
*   **Method:** `POST`
*   **Description:** Authenticates a user and returns JWT access and refresh tokens. **User must be verified to login.**
*   **Input Data (JSON):**
    *   `username` (string, required): Can be the user's **Username**, **Email**, or **Phone Number**.
    *   `password` (string, required)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"refresh": "REFRESH_TOKEN", "access": "ACCESS_TOKEN"}`
*   **Failure Response:**
    *   **Status Code:** `401 Unauthorized`
    *   **Reason:** Invalid credentials or account not verified.

### Token Refresh
*   **URL:** `/api/users/token/refresh/`
*   **Method:** `POST`
*   **Description:** Provides a new access token using a valid refresh token.
*   **Input Data (JSON):**
    *   `refresh` (string, required)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"access": "NEW_ACCESS_TOKEN"}`

### User Profile
*   **URL:** `/api/users/profile/`
*   **Method:** `GET`, `PUT`, `PATCH`
*   **Auth Required:** Yes
*   **Description:** Retrieves or updates the current user's profile information (username and phone number).
*   **Input Data (PUT/PATCH JSON):**
    *   `username` (string, optional)
    *   `phone_number` (string, optional)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"username": "...", "phone_number": "...", "email": "..."}`

---

## 2. Content Management (Posts & Categories)

### Create Post
*   **URL:** `/api/content/posts/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** Creates a new main post. Uploads are restricted by a time window defined in `AppSettings`. Media size is validated.
*   **Input Data (Multipart/Form-Data):**
    *   `category` (integer, ID, required)
    *   `media_file` (file, required)
    *   `caption` (string, required)
*   **Success Response:**
    *   **Status Code:** `201 Created`
    *   **Data:** Serialized post object.
*   **Failure Response:**
    *   **Status Code:** `400 Bad Request`
    *   **Reason:** Outside upload window, file too large, or missing data.

### Get Post Feed
*   **URL:** `/api/content/feed/`
*   **Method:** `GET`
*   **Auth Required:** No
*   **Description:** Returns a list of all posts that have not had their media deleted, ordered by most recent.
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** List of post objects (includes author, category, media_url, caption, status, avg_rating, vote_count, and sub_posts).

### Get Trending Feed
*   **URL:** `/api/content/trending/`
*   **Method:** `GET`
*   **Auth Required:** No
*   **Description:** Returns the top 10 "Active" or "Trending" posts ordered by average rating and vote count.
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** List of top 10 post objects.

### Create Sub-Post (Reply)
*   **URL:** `/api/content/subposts/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** Creates a media-based reply to an existing post.
*   **Input Data (Multipart/Form-Data):**
    *   `parent_post` (integer, ID, required)
    *   `media_file` (file, required)
    *   `caption` (string, optional)
*   **Success Response:**
    *   **Status Code:** `201 Created`
    *   **Data:** Serialized sub-post object.

### List Categories
*   **URL:** `/api/content/categories/`
*   **Method:** `GET`
*   **Auth Required:** No
*   **Description:** Returns a list of all available post categories.
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `[{"id": 1, "name": "Category Name", "slug": "category-name"}, ...]`

---

## 3. Social Interactions (Buddies & Voting)

### Send Buddy Request
*   **URL:** `/api/social/buddies/request/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** Sends a friend request to another user.
*   **Input Data (JSON):**
    *   `receiver` (integer, User ID, required)
*   **Success Response:**
    *   **Status Code:** `201 Created`
    *   **Data:** Serialized request object.

### Respond to Buddy Request
*   **URL:** `/api/social/buddies/respond/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** Accepts or rejects an incoming buddy request.
*   **Input Data (JSON):**
    *   `request_id` (integer, required)
    *   `action` (string: "accepted" or "rejected", required)
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"message": "Request accepted/rejected."}`
*   **Failure Response:**
    *   **Status Code:** `404 Not Found` (if request doesn't exist or isn't for the current user).

### List Incoming Requests
*   **URL:** `/api/social/buddies/requests/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists all pending buddy requests received by the current user.
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** List of pending buddy request objects.

### List Buddies
*   **URL:** `/api/social/buddies/list/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Lists all users who are mutual "buddies" (accepted requests).
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** List of user objects (minimal details).

### Manage Close Buddies (Inner Circle)
*   **URL:** `/api/social/close-buddies/`
*   **Method:** `GET`, `POST`
*   **Auth Required:** Yes
*   **Description:**
    *   `GET`: Lists all users in the current user's "Inner Circle" (max 5).
    *   `POST`: Adds a buddy to the Inner Circle. Automatically ensures they are a mutual buddy.
*   **Input Data (POST JSON):**
    *   `buddy` (integer, User ID, required)
*   **Success Response (POST):**
    *   **Status Code:** `201 Created`
*   **Failure Response (POST):**
    *   **Status Code:** `400 Bad Request`
    *   **Reason:** Adding self, already in inner circle, or exceeding the limit of 5.

### Approve Post
*   **URL:** `/api/social/approve-post/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** A "Close Buddy" approves a post, moving it towards "Active" status.
*   **Input Data (JSON):**
    *   `post` (integer, ID, required)
*   **Failure Response:**
    *   **Status Code:** `400 Bad Request`
    *   **Reason:** User is not a close buddy of the post author.

### Vote on Post
*   **URL:** `/api/social/vote/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** Casts a rating (1-5) on a post.
*   **Input Data (JSON):**
    *   `post` (integer, ID, required)
    *   `value` (integer, 1 to 5, required)
*   **Success Response:**
    *   **Status Code:** `201 Created`

---

## 4. Core Features (Notifications & Reporting)

### List Notifications
*   **URL:** `/api/core/notifications/`
*   **Method:** `GET`
*   **Auth Required:** Yes
*   **Description:** Returns all notifications for the authenticated user, ordered by most recent.
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** List of notification objects (includes actor, verb, target, read_status).

### Mark Notification as Read
*   **URL:** `/api/core/notifications/<id>/read/`
*   **Method:** `PUT` / `PATCH`
*   **Auth Required:** Yes
*   **Description:** Marks a specific notification as read.
*   **Success Response:**
    *   **Status Code:** `200 OK`
    *   **Data:** `{"status": "notification marked as read"}`
*   **Failure Response:**
    *   **Status Code:** `403 Forbidden` (if the notification doesn't belong to the user).

### Report Content
*   **URL:** `/api/core/report/`
*   **Method:** `POST`
*   **Auth Required:** Yes
*   **Description:** Files a report against a post or other content.
*   **Input Data (JSON):**
    *   `content_type` (integer, ContentType ID, required)
    *   `object_id` (integer, ID of the post/content, required)
    *   `reason` (string, required)
*   **Success Response:**
    *   **Status Code:** `201 Created`
    *   **Data:** Serialized report object.

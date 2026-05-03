# Branching Structure

---

## Overview

This document outlines the branching strategy using Git Flow, tailored for integration with GitHub Projects.

---

## Branch Structure

### Main
- Represents production-ready code  
- Must contain only stable commits  

---

### Dev
- Integration branch for new features  
- Contains the complete project history  
- May include features that are not yet released  

---

### Feature branches
- Created from the `dev` branch  
- Used for developing new functionalities  
- Once completed, they must be merged back into `dev`  

---

## Naming Conventions

Branch names must include the task ID (ticket/issue) to ensure traceability.

---

### General Pattern

`[ticket-id]-[short-task-title]`

**Examples:**
- `pk-32-download-gdb`  
- `pk-15-create-user-auth`  

---

### Research/Study Branches (Spike)

`spike-[us-id]-[us-title]`

**Example:**
- `spike-us-01-download-pdf`  

---

## Guidelines

- Replace spaces with hyphens (`-`)  
- Do not use uppercase letters  
- Avoid special characters  
- Always include the task ID in the branch name  
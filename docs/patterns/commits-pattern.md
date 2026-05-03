# Commit Pattern

To ensure a clean, readable, and consistent commit history, we follow a convention based on Conventional Commits, adapted to include the issue ID.

---

## Commit Structure

`type(ticket_id): description`

---

## Commit Message Components

### Type
Required. Indicates the nature of the change.

**Allowed types:**

- `feat`: New feature  
- `fix`: Bug fix  
- `docs`: Documentation changes  
- `style`: Formatting changes with no impact on logic  
- `refactor`: Code refactoring without adding features or fixing bugs  
- `test`: Adding or updating tests  
- `chore`: Changes to build processes, scripts, or auxiliary tools  
- `ci`: Changes to CI configuration files  
- `perf`: Performance improvements  
- `build`: Changes to build system or dependencies  
- `revert`: Reverts a previous commit  

---

### ticket_id
- Identifier of the related issue  
- Must be enclosed in parentheses `()`  

---

### description
- Brief explanation of the change  
- Written in English  
- Use lowercase letters (except for proper nouns)  
- Must be clear and concise  

---

## Examples

### New feature
`feat(#3): add form to create a new user`

### Bug fix
`fix(#5): fix button alignment on home page`

### Refactoring
`refactor(#12): optimize product search query`

---

## Best Practices

- Keep the description within a maximum of 50 characters  
- Use clear and objective language  
- For more detailed descriptions:  
  - Add a blank line after the title  
  - Include an explanatory body  
  - Use lines with up to 72 characters  
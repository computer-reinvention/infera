# Task: Destroy Infrastructure

**WARNING: This action is irreversible.**

## Step 1: Read Configuration

Read the config at {project_root}/.infera/config.yaml to identify resources to delete.

## Step 2: List Resources

Show the user what will be deleted.

## Step 3: Confirm

Use AskUserQuestion:
> "I'm about to delete the following resources. This cannot be undone. Are you sure?"
> 1. Yes, delete everything
> 2. No, cancel

If user cancels, exit immediately.

## Step 4: Destroy

{destroy_commands}

## Step 5: Handle Results

{include:_shared/error_loop.md}

### On Success

Confirm deletion:
> "All resources have been deleted."

**Exit the loop.**

## Important

- **Always confirm before deleting** - deletions are irreversible
- **Delete in reverse dependency order** - dependent resources before their dependencies
- **Keep looping** until success or user stops

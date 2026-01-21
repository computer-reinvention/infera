# Task: Generate Infrastructure Plan

## Step 1: Read Configuration

Read the config at {project_root}/.infera/config.yaml

## Step 2: Validate Prerequisites

{prerequisites}

## Step 3: Generate Configuration

{generate_config}

## Step 4: Validate Configuration

{validate_config}

## Step 5: Handle Results

{include:_shared/error_loop.md}

### On Success

Report what will be deployed:
- Resources to be created
- Estimated costs (if applicable)
- Any warnings or recommendations

**Exit the loop.**

# Interactive Error Handling Loop

**This is an interactive loop. Keep trying until success or the user decides to stop.**

```
while true:
    1. Run the operation
    2. Check results
    3. If success → done, exit loop
    4. If error → analyze, offer fix, ask user
    5. If user wants fix → apply fix, go back to step 1
    6. If user wants to stop → exit loop
```

## On Error

1. **Analyze the error** (read {templates_dir}/instructions/error_handling.md if needed)
2. **Explain clearly** what went wrong (in plain, non-technical language)
3. **Offer a specific fix** (CLI commands you can run)
4. **Use AskUserQuestion** to ask:
   > "Would you like me to try to fix this?"
   > 1. Yes, fix it and retry
   > 2. No, I'll handle it manually

5. **If user says yes:**
   - Run the CLI commands to fix the issue
   - **Go back and retry the operation**

6. **If user says no:**
   - Exit the loop

## Important

- **Keep looping** until success or user stops
- **Always ask before giving up** - use AskUserQuestion
- **After applying a fix, always retry** the operation
- The user should never be left with a failed state without being asked if they want help

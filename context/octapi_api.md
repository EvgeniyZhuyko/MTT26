# Octapi Lua Sandbox — API Reference

## Lua Version

Lua 5.x

## Variable Namespaces

All workflow variables are accessed through two namespaces:

- `wf.vars.*` — LowCode variables declared in the workflow schema.
- `wf.initVariables.*` — variables passed to the workflow at start time.

**Never** access variables as bare names. Always use the full path.

```lua
-- Correct
local emails = wf.vars.emails
local ts     = wf.initVariables.recallTime

-- Wrong (bare names are nil in the sandbox)
local emails = emails
```

## Custom Globals

Two utility functions are available for array handling:

```lua
-- Create a new empty array (use instead of plain {})
local result = _utils.array.new()

-- Mark an existing table as an array (for serialisation)
_utils.array.markAsArray(result)
```

Use `_utils.array.new()` whenever building a result array that will be
returned from the script. Plain `{}` tables are serialised as objects, not
arrays, by the platform.

## Forbidden Constructs

The sandbox does **not** allow:

- `require("...")` — no module loading
- `io.*`, `os.*`, `file.*` — no file system access
- `dofile()`, `loadfile()`, `load()` — no dynamic loading
- JsonPath syntax (`$.field`, `$['field']`) — use direct Lua field access

## Code Style Rules

1. Declare all variables with `local`.
2. The script must end with a `return` statement.
3. Scripts are embedded as a JSON string in the format `lua{...}lua` in the
   Octapi manifest — keep the code compact.

## Examples

### 1. Last element of an array

```lua
return wf.vars.emails[#wf.vars.emails]
```

### 2. Increment a counter

```lua
return wf.vars.try_count_n + 1
```

### 3. Filter array — keep items with a non-empty Discount or Markdown field

```lua
local result = _utils.array.new()
local items  = wf.vars.parsedCsv

for _, item in ipairs(items) do
  if (item.Discount ~= "" and item.Discount ~= nil) or
     (item.Markdown ~= "" and item.Markdown ~= nil) then
    table.insert(result, item)
  end
end

return result
```

### 4. Clear specific keys from each object in a result array

```lua
local result = wf.vars.RESTbody.result

for _, entry in pairs(result) do
  for key, _ in pairs(entry) do
    if key ~= "ID" and key ~= "ENTITY_ID" and key ~= "CALL" then
      entry[key] = nil
    end
  end
end

return result
```

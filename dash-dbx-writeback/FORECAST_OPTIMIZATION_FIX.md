# Forecast Optimization Fix

## Problem Summary

The error `"No forecast data found for ID: FCST-20260108-5fe6f0af"` occurred because:

1. **Database Write Failed**: The forecast submission attempted to write to the database but failed due to connection timeout
2. **Error Handling Bug**: The code didn't check if the write was successful before proceeding with optimization
3. **Connection Pool Exhaustion**: The connection pool ran out of available connections (timeout after 30 seconds)

## Root Causes

### 1. Unchecked Write Result
The `insert_overwrite_table()` function returns:
- `int` (row count) on success
- `tuple (error_message, 0)` on failure

But the code in `input_callbacks.py` wasn't checking the return value, so it proceeded with optimization even when the database write failed.

### 2. Connection Pool Issues
- The connection pool was configured with only 5 max connections
- Long-running queries or connections not being returned properly caused pool exhaustion
- No timeout configured for waiting for connections

## Fixes Applied

### 1. Added Error Handling in Forecast Submission
**File**: `src/dash_dbx_writeback/callbacks/input_callbacks.py`

```python
# Now checks the return value from insert_overwrite_table
write_result = insert_overwrite_table(...)

if isinstance(write_result, tuple):
    # Write failed - show error and don't proceed
    error_msg, _ = write_result
    return error_alert
    
# Write successful - proceed with optimization
row_count = write_result
```

**Benefits**:
- Forecast submission now fails gracefully if database write fails
- User sees a clear error message
- Optimization is NOT triggered if forecast data wasn't saved
- Submit button remains enabled to allow retry

### 2. Improved Connection Pool Configuration
**File**: `src/dash_dbx_writeback/config.py`

**Changes**:
- Increased `POOL_MIN_SIZE` from 1 to 2
- Increased `POOL_MAX_SIZE` from 5 to 10
- Added `POOL_TIMEOUT` of 60 seconds

**Benefits**:
- More connections available for concurrent operations
- Better timeout configuration
- Can be tuned via environment variables if needed

### 3. Created Regeneration Utility
**File**: `regenerate_optimizations.py`

A utility script to regenerate stock optimizations for forecasts that failed.

## How to Fix Your Current Issue

### Option 1: Use the Regeneration Script

For the specific forecast ID that failed:

```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-dbx-writeback

# For a specific forecast ID
uv run python regenerate_optimizations.py FCST-20260108-5fe6f0af

# Or regenerate all forecasts missing optimization
uv run python regenerate_optimizations.py --all-missing
```

### Option 2: Resubmit the Forecast

1. Navigate to the input page in the app
2. Load the same data
3. Click Submit again

With the new error handling:
- If the database write fails, you'll see a clear error message
- You can retry the submission
- Optimization will only run if the data is successfully written

## Verification

After the fix, you can verify optimization was successful:

```python
from src.dash_dbx_writeback.ml.forecast_optimizer import get_optimization_results

# Check if optimization exists for your forecast
results = get_optimization_results("FCST-20260108-5fe6f0af")
print(f"Found {len(results)} optimization results")
```

## Prevention for Future

### Environment Variables (Optional)

You can tune connection pool settings if needed:

```bash
# Increase max connections if you have high concurrent load
export POOL_MAX_SIZE=20

# Increase timeout if operations are slow
export POOL_TIMEOUT=90.0

# Keep more minimum connections ready
export POOL_MIN_SIZE=5
```

### Monitoring

Watch for these log patterns that indicate issues:

- `✗ insert_overwrite_table: Failed to write table:` - Database write failure
- `couldn't get a connection after X.XX sec` - Connection pool exhaustion
- `❌ Error running stock optimization: No forecast data found` - Missing forecast data

### Best Practices

1. **Always check the logs** - The timestamp logs show exactly what happened
2. **Connection pool sizing** - If you see frequent timeouts, increase `POOL_MAX_SIZE`
3. **Retry failed forecasts** - Use `regenerate_optimizations.py` for easy recovery
4. **Database connectivity** - Ensure stable network connection to Databricks

## Testing the Fix

To test that the fix works:

1. **Test successful submission**:
   - Submit a forecast with valid data
   - Verify both forecast data and optimization results are saved

2. **Test failure handling**:
   - Simulate a database failure (disconnect network temporarily)
   - Verify error message is displayed
   - Verify optimization is NOT attempted
   - Verify submit button remains enabled for retry

3. **Test regeneration**:
   - Use `regenerate_optimizations.py --all-missing`
   - Verify it finds and processes missing optimizations

## Related Files

- `src/dash_dbx_writeback/callbacks/input_callbacks.py` - Forecast submission callback
- `src/dash_dbx_writeback/ml/forecast_optimizer.py` - Optimization logic
- `src/dash_dbx_writeback/database_operations.py` - Database operations
- `src/dash_dbx_writeback/config.py` - Database configuration
- `regenerate_optimizations.py` - Utility to regenerate optimizations

## Questions?

If you encounter issues:
1. Check the terminal logs for detailed error messages
2. Look for connection pool timeout messages
3. Try the regeneration script for failed forecasts
4. Consider increasing `POOL_MAX_SIZE` if timeouts persist


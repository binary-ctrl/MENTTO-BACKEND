-- Migration script to update user_time_slots table for simplified weekly recurring structure
-- This changes from storing specific dates to storing day of week + time ranges

-- Step 1: Create backup of existing data (optional)
-- CREATE TABLE user_time_slots_backup AS SELECT * FROM user_time_slots;

-- Step 2: Drop existing table
DROP TABLE IF EXISTS user_time_slots;

-- Step 3: Create new simplified table structure
CREATE TABLE user_time_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Simplified structure for weekly recurring slots
    day_of_week INTEGER NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6), -- 0=Monday, 6=Sunday
    start_time TIME NOT NULL, -- Time in HH:MM format
    end_time TIME NOT NULL, -- Time in HH:MM format
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    
    -- Slot metadata
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'booked', 'blocked', 'cancelled')),
    
    -- Recurring information
    is_recurring BOOLEAN NOT NULL DEFAULT true,
    recurring_pattern VARCHAR(20) DEFAULT 'weekly' CHECK (recurring_pattern IN ('weekly', 'daily', 'monthly')),
    
    -- Duration calculated automatically
    duration_minutes INTEGER NOT NULL,
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT check_start_before_end CHECK (start_time < end_time),
    CONSTRAINT check_duration_positive CHECK (duration_minutes > 0),
    CONSTRAINT unique_user_day_time UNIQUE (user_id, day_of_week, start_time, end_time)
);

-- Step 4: Create indexes for better performance
CREATE INDEX idx_user_time_slots_user_id ON user_time_slots(user_id);
CREATE INDEX idx_user_time_slots_day_of_week ON user_time_slots(day_of_week);
CREATE INDEX idx_user_time_slots_status ON user_time_slots(status);
CREATE INDEX idx_user_time_slots_user_day ON user_time_slots(user_id, day_of_week);

-- Step 5: Create trigger to automatically update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_time_slots_updated_at 
    BEFORE UPDATE ON user_time_slots 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Step 6: Add comments for documentation
COMMENT ON TABLE user_time_slots IS 'User-defined weekly recurring time slots for mentoring calls';
COMMENT ON COLUMN user_time_slots.day_of_week IS 'Day of week: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday';
COMMENT ON COLUMN user_time_slots.start_time IS 'Start time in HH:MM format (24-hour)';
COMMENT ON COLUMN user_time_slots.end_time IS 'End time in HH:MM format (24-hour)';
COMMENT ON COLUMN user_time_slots.timezone IS 'Timezone for the time slots (e.g., Asia/Kolkata)';
COMMENT ON COLUMN user_time_slots.duration_minutes IS 'Duration of the slot in minutes (calculated from start_time and end_time)';
COMMENT ON COLUMN user_time_slots.is_recurring IS 'Whether this is a recurring slot (always true for weekly slots)';
COMMENT ON COLUMN user_time_slots.recurring_pattern IS 'Pattern of recurrence (weekly, daily, monthly)';

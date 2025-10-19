-- Migration script to create user_time_slots table
-- This table stores user-created time slots for taking calls

CREATE TABLE IF NOT EXISTS user_time_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'booked', 'blocked', 'cancelled')),
    is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
    recurring_pattern VARCHAR(20) CHECK (recurring_pattern IN ('daily', 'weekly', 'monthly')),
    recurring_end_date TIMESTAMPTZ,
    duration_minutes INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_user_time_slots_user_id ON user_time_slots(user_id);
CREATE INDEX IF NOT EXISTS idx_user_time_slots_start_time ON user_time_slots(start_time);
CREATE INDEX IF NOT EXISTS idx_user_time_slots_end_time ON user_time_slots(end_time);
CREATE INDEX IF NOT EXISTS idx_user_time_slots_status ON user_time_slots(status);
CREATE INDEX IF NOT EXISTS idx_user_time_slots_user_start ON user_time_slots(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_user_time_slots_user_status ON user_time_slots(user_id, status);

-- Create a function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_user_time_slots_updated_at 
    BEFORE UPDATE ON user_time_slots 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE user_time_slots IS 'Stores user-created time slots for taking calls';
COMMENT ON COLUMN user_time_slots.id IS 'Unique identifier for the time slot';
COMMENT ON COLUMN user_time_slots.user_id IS 'Reference to the user who created this slot';
COMMENT ON COLUMN user_time_slots.start_time IS 'Start time of the slot (stored in UTC)';
COMMENT ON COLUMN user_time_slots.end_time IS 'End time of the slot (stored in UTC)';
COMMENT ON COLUMN user_time_slots.timezone IS 'Timezone for the slot (e.g., UTC, Asia/Kolkata)';
COMMENT ON COLUMN user_time_slots.title IS 'Optional title for the slot';
COMMENT ON COLUMN user_time_slots.description IS 'Optional description for the slot';
COMMENT ON COLUMN user_time_slots.status IS 'Current status of the slot (available, booked, blocked, cancelled)';
COMMENT ON COLUMN user_time_slots.is_recurring IS 'Whether this is a recurring slot';
COMMENT ON COLUMN user_time_slots.recurring_pattern IS 'Pattern for recurring slots (daily, weekly, monthly)';
COMMENT ON COLUMN user_time_slots.recurring_end_date IS 'End date for recurring slots';
COMMENT ON COLUMN user_time_slots.duration_minutes IS 'Duration of the slot in minutes';
COMMENT ON COLUMN user_time_slots.created_at IS 'When the slot was created';
COMMENT ON COLUMN user_time_slots.updated_at IS 'When the slot was last updated';

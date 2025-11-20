-- Add payment_status column to sessions table
-- This column tracks the payment status: 'pending', 'success', or 'failed'

ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'pending';

-- Add a check constraint to ensure only valid values are allowed
ALTER TABLE sessions
ADD CONSTRAINT check_payment_status 
CHECK (payment_status IN ('pending', 'success', 'failed'));

-- Update existing sessions to have 'pending' status if they don't have payment_status set
UPDATE sessions
SET payment_status = 'pending'
WHERE payment_status IS NULL;

-- Optional: Create an index on payment_status for better query performance
CREATE INDEX IF NOT EXISTS idx_sessions_payment_status ON sessions(payment_status);

-- Optional: Add a comment to document the column
COMMENT ON COLUMN sessions.payment_status IS 'Payment status for the session: pending (default), success (payment verified), or failed';


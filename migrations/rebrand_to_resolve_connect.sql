-- Migration: Rebrand from Learn/Fun to Resolve/Connect
-- Run this SQL script against the database to update enum values

-- Step 1: Update CreatorVertical enum values
ALTER TYPE creatorvertical RENAME VALUE 'learn' TO 'resolve';
ALTER TYPE creatorvertical RENAME VALUE 'fun' TO 'connect';

-- Step 2: Update PackageType enum values  
ALTER TYPE packagetype RENAME VALUE 'consultation' TO 'resolution';
ALTER TYPE packagetype RENAME VALUE 'shoutout' TO 'greeting';
ALTER TYPE packagetype RENAME VALUE 'tier' TO 'membership';

-- Step 3: Verify changes
SELECT enumlabel FROM pg_enum WHERE enumtypid = 'creatorvertical'::regtype;
SELECT enumlabel FROM pg_enum WHERE enumtypid = 'packagetype'::regtype;

-- Step 4: Update any existing data (if needed)
-- This will update any profiles that might have old values
UPDATE creator_profiles SET vertical = 'connect' WHERE vertical = 'fun';
UPDATE creator_profiles SET vertical = 'resolve' WHERE vertical = 'learn';

UPDATE service_packages SET package_type = 'resolution' WHERE package_type = 'consultation';
UPDATE service_packages SET package_type = 'greeting' WHERE package_type = 'shoutout';
UPDATE service_packages SET package_type = 'membership' WHERE package_type = 'tier';

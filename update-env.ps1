# Update .env file with correct database URL
$envContent = Get-Content .env.example
$envContent | Set-Content .env -Force

Write-Host "✅ Updated .env file with async PostgreSQL driver"
Write-Host "📝 DATABASE_URL=postgresql+asyncpg://onlyforu_user:onlyforu_dev_password@localhost:5432/onlyforu_db"

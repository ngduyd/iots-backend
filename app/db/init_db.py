import bcrypt

from app.db.session import get_db_pool, fetchrow, execute

async def init_db():
    pool = await get_db_pool()
    if pool is None:
        return

    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS groups (
                        group_id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS branches (
                        branch_id SERIAL PRIMARY KEY,
                        group_id INT REFERENCES groups(group_id),
                        name VARCHAR(100) NOT NULL,
                        thresholds JSONB,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE branches ADD COLUMN IF NOT EXISTS thresholds JSONB;
                    """
                )
                await connection.execute(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='branches' AND column_name='metadata') THEN
                            ALTER TABLE branches RENAME COLUMN metadata TO thresholds;
                        END IF;
                    END $$;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        alert_id SERIAL PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id) ON DELETE CASCADE,
                        message TEXT NOT NULL,
                        level VARCHAR(50) NOT NULL,
                        is_read BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE alerts
                    ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT FALSE;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id SERIAL PRIMARY KEY,
                        group_id INT REFERENCES groups(group_id),
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role VARCHAR(20) DEFAULT 'user' NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        session_id VARCHAR(128) PRIMARY KEY,
                        user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        expires_at TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sensors (
                        sensor_id VARCHAR(32) PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id),
                        name VARCHAR(50),
                        status VARCHAR(100) DEFAULT 'offline' NOT NULL,
                        deleted_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id UUID PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id) ON DELETE CASCADE,
                        user_id INT REFERENCES users(user_id) ON DELETE SET NULL,
                        secret VARCHAR(255) NOT NULL,
                        dataset_params JSONB,
                        feature_engineering_params JSONB,
                        forecast_params JSONB,
                        model_hyperparams JSONB,
                        status VARCHAR(50) DEFAULT 'pending' NOT NULL,
                        message TEXT,
                        result JSONB,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE sensors
                    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS values (
                        id BIGSERIAL PRIMARY KEY,
                        sensor_id VARCHAR(32) REFERENCES sensors(sensor_id),
                        value JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cameras (
                        camera_id VARCHAR(32) PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id),
                        name VARCHAR(50),
                        secret VARCHAR(64),
                        activate BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE jobs
                    ADD COLUMN IF NOT EXISTS message TEXT;
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE cameras
                    ADD COLUMN IF NOT EXISTS activate BOOLEAN NOT NULL DEFAULT FALSE;
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE cameras
                    ADD COLUMN IF NOT EXISTS status VARCHAR(100) DEFAULT 'offline' NOT NULL;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS camera_access_requests (
                        request_id SERIAL PRIMARY KEY,
                        camera_id VARCHAR(32) REFERENCES cameras(camera_id) ON DELETE CASCADE,
                        user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
                        status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                        access_token VARCHAR(128),
                        expires_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS image_analysis (
                        image_id VARCHAR(64) PRIMARY KEY,
                        camera_id VARCHAR(32) REFERENCES cameras(camera_id) ON DELETE SET NULL,
                        image_path VARCHAR(255),
                        people_count INT DEFAULT 0,
                        metadata JSONB,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sensor_time_desc ON values(sensor_id, created_at DESC);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sensors_active_branch_updated
                    ON sensors(branch_id, updated_at)
                    WHERE deleted_at IS NULL;
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sensors_active_updated
                    ON sensors(updated_at)
                    WHERE deleted_at IS NULL;
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_camera_access_requests_token
                    ON camera_access_requests(access_token);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_image_analysis_camera ON image_analysis(camera_id);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_image_analysis_created ON image_analysis(created_at DESC);
                    """
                )
                await connection.execute(
                    """
                    CREATE OR REPLACE FUNCTION sync_sensor_status_from_value()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        UPDATE sensors
                        SET status = 'online',
                            updated_at = NOW()
                        WHERE sensor_id = NEW.sensor_id
                          AND deleted_at IS NULL
                          AND status IS DISTINCT FROM 'online';

                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                    """
                )
                await connection.execute(
                    """
                    DROP TRIGGER IF EXISTS trg_sync_sensor_status_from_value ON values;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS models (
                        model_id UUID PRIMARY KEY,
                        group_id INT REFERENCES groups(group_id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE jobs
                    ADD COLUMN IF NOT EXISTS model_id UUID REFERENCES models(model_id);
                    """
                )
                await connection.execute(
                    """
                    CREATE TRIGGER trg_sync_sensor_status_from_value
                    AFTER INSERT ON values
                    FOR EACH ROW
                    EXECUTE FUNCTION sync_sensor_status_from_value();
                    """
                )
    except Exception as e:
        print(f"Error initializing the database: {e}")

async def ensure_default_admin_user():
    try:
        # Check superadmin
        superadmin = await fetchrow("SELECT user_id, role FROM users WHERE username = $1;", "superadmin")
        if superadmin:
            if superadmin["role"] != "superadmin":
                await execute("UPDATE users SET role = 'superadmin' WHERE user_id = $1;", superadmin["user_id"])
        else:
            pwd_hash = bcrypt.hashpw("superadmin123".encode(), bcrypt.gensalt()).decode()
            await execute(
                "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, 'superadmin');",
                "superadmin", pwd_hash
            )

        # Check admin
        admin = await fetchrow("SELECT user_id, role FROM users WHERE username = $1;", "admin")
        if admin:
            if admin["role"] != "admin":
                await execute("UPDATE users SET role = 'admin' WHERE user_id = $1;", admin["user_id"])
        else:
            pwd_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            await execute(
                "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, 'admin');",
                "admin", pwd_hash
            )

        return True
    except Exception as e:
        print(f"Error ensuring default admin user: {e}")
        return False

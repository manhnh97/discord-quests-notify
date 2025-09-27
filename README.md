# Discord Quests Notify

A comprehensive Python tool for fetching Discord quests and sending them as webhooks with automatic duplicate prevention and beautiful Discord embeds.

## Features

- 🎮 **Quest Tracking**: Automatically tracks Discord quests and prevents duplicate notifications
- 🔄 **Smart Sync**: Syncs with Discord API to automatically remove quests that are no longer available
- 📱 **Discord Integration**: Sends quest notifications via Discord webhooks with rich embeds
- 🎨 **Beautiful Embeds**: Creates visually appealing Discord embeds with quest details, images, and links
- ⚡ **Rate Limiting**: Built-in rate limiting to respect Discord API limits
- 🗄️ **SQLite Database**: Uses SQLite for efficient quest tracking and persistence
- 🔧 **Flexible Configuration**: Environment-based configuration for easy deployment
- 🚨 **Alert System**: Built-in Discord webhook alerts for error monitoring and system notifications
- 🔍 **Quest Detection**: Fixed logic to properly detect new quests even after database modifications

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd discord-quests-notify
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```env
   DISCORD_AUTHORIZATION=your_discord_authorization_token_from_dev_console_api_@me
   TOKEN_JWT=your_discord_jwt_token_from_dev_console_api_@me
   WEBHOOK_URL=your_discord_webhook_url
   WEBHOOK_URL_ALERT=your_alert_webhook_url_for_errors
   ```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_AUTHORIZATION` | Discord authorization token for API access | Yes |
| `TOKEN_JWT` | Discord JWT token for API requests | Yes |
| `WEBHOOK_URL` | Discord webhook URL for sending notifications | Yes |
| `WEBHOOK_URL_ALERT` | Discord webhook URL for error alerts (optional) | No |

### Getting Discord Tokens

1. **Authorization Token**: Extract from Discord client requests
2. **JWT Token**: Found in Discord client's x-super-properties header
3. **Webhook URL**: Create a webhook in your Discord server settings

## Usage

### Basic Usage

Run the main script to fetch quests and send notifications:

```bash
python main.py
```

### Command Line Options

The script supports several functions that can be called programmatically:

#### Send All Quests
```python
from main import send_all_quests_webhook
send_all_quests_webhook(webhook_url="your_webhook_url", new_only=True)
```

#### Send Single Quest
```python
from main import send_single_quest_webhook
send_single_quest_webhook(quest_id="quest_id_here", webhook_url="your_webhook_url")
```

#### Test Webhook
```python
from main import test_button_webhook
test_button_webhook(webhook_url="your_webhook_url")
```

#### Manage Quest Tracking
```python
from main import show_seen_quests, reset_seen_quests, cleanup_old_quests

# Show currently tracked quests
show_seen_quests()

# Reset all tracked quests (mark all as new)
reset_seen_quests()

# Sync with current API (remove quests no longer available)
cleanup_old_quests()
```

## Quest Tracking System

The application uses a sophisticated quest tracking system:

### SQLite Database
- **Location**: `db/seen_quests.db`
- **Schema**: Stores quest IDs with timestamps
- **Primary Storage**: Database is the main storage system for quest tracking

### Smart Sync Algorithm
1. **Load Current State**: Loads existing quest IDs from database
2. **Detect New Quests**: Compares API response with current database state
3. **Add New Quests**: Immediately adds newly detected quests to database
4. **Sync Database**: Removes quests no longer available in API response
5. **Duplicate Prevention**: Only sends notifications for truly new quests

### Quest Lifecycle
```
API Response → Load Database State → Detect New Quests → Add to Database → Sync Database → Send Notifications
```

## Discord Embed Features

Each quest notification includes:

- 🎯 **Quest Information**: Name, game title, publisher
- 📅 **Timing**: Start and end dates in Vietnam timezone
- 📝 **Tasks**: Detailed task list with emojis and durations
- 🎁 **Rewards**: Available rewards for completion
- 🖼️ **Images**: Hero image and reward thumbnails
- 🔗 **Links**: Direct link to quest page

### Task Types Supported
- 📺 Watch Video
- 🖥️ Play on Desktop
- 📡 Stream on Desktop
- 🎮 Play Activity
- 📱 Watch Video on Mobile

## File Structure

```
discord-quests-notify/
├── main.py                 # Main application logic
├── seen_quests.py          # Quest tracking database functions
├── requirements.txt         # Python dependencies
├── .env                    # Environment configuration
├── db/
│   └── seen_quests.db      # SQLite database for quest tracking
└── README.md               # This file
```

## API Integration

### Discord API Endpoints
- **Quests Endpoint**: `https://discord.com/api/v10/quests/@me`
- **Quest Pages**: `https://discord.com/quests/{quest_id}`
- **CDN Images**: `https://cdn.discordapp.com/quests/{quest_id}/{image_path}`

### Rate Limiting
- **Webhook Delay**: 1 second between webhook sends
- **API Respect**: Follows Discord API rate limits
- **Error Handling**: Graceful handling of API errors

## Deployment

### Cron Job Setup
Create a cron job to run the script periodically:

```bash
# Run every hour
0 * * * * cd /path/to/discord-quests-notify && python main.py

# Run every 5 minutes
*/5 * * * * cd /path/to/discord-quests-notify && python main.py
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

## Troubleshooting

### Common Issues

1. **No Quests Found**
   - Check Discord authorization tokens
   - Verify API endpoint accessibility
   - Check network connectivity

2. **Webhook Failures**
   - Verify webhook URL is correct
   - Check Discord server permissions
   - Ensure webhook is not rate limited

3. **Database Issues**
   - Check file permissions for `db/` directory
   - Verify SQLite database is not corrupted
   - Check disk space availability

4. **Quest Detection Issues**
   - If quests aren't detected as new after database changes, the sync logic has been fixed
   - The system now properly detects new quests even after manual database modifications
   - Use `cleanup_old_quests()` to sync with current API state

### Debug Mode
Enable debug logging by modifying the logging level in `main.py`:

```python
logger.setLevel(logging.DEBUG)
```

### Alert System
The system includes a built-in alert system that sends error notifications to Discord:
- **Error Monitoring**: Automatically sends ERROR+ level logs to configured webhook
- **Token Validation**: Alerts when Discord tokens are missing or invalid
- **API Failures**: Notifies about authentication and API request failures
- **Fallback Support**: Uses `WEBHOOK_URL` if `WEBHOOK_URL_ALERT` is not configured

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Please check the license file for details.

## Recent Updates

### v1.1.0 - Quest Detection Fix
- **Fixed Quest Detection Logic**: Resolved issue where quests weren't detected as new after database modifications
- **Improved Sync Algorithm**: Reordered operations to properly detect new quests before database sync
- **Enhanced Error Handling**: Added comprehensive error monitoring and Discord alert system
- **Better Logging**: Improved logging with detailed quest tracking information

### Key Improvements
- Quest detection now works correctly when manually deleting records from database
- Alert system provides real-time error notifications via Discord webhooks
- More robust error handling for API failures and token issues
- Better documentation and troubleshooting guides

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the code comments
3. Open an issue on the repository

---

**Note**: This tool requires valid Discord tokens and should be used responsibly in accordance with Discord's Terms of Service.
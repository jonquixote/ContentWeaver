import os

import uvicorn

if __name__ == '__main__':
    uvicorn.run(
        'fastapi_app.main:app',
        host='0.0.0.0',
        port=int(os.getenv('PORT', '5004')),
    )

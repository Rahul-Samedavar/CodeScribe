"""This module is the entry point for the application, responsible for running the server."""
import uvicorn
if __name__ == '__main__':
    uvicorn.run('server.main:app', host='0.0.0.0', port=8000, reload=True)
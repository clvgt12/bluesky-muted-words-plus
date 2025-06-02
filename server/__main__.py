# __main__.py
from server.app import app
from waitress import serve

if __name__ == '__main__':
    serve(app, host='127.0.0.1', port=8000, threads=4)

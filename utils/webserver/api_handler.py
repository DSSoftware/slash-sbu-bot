import flask
from flask import request, jsonify
from utils.database import BannedMemberInfo, DBConnection, convert_to_banned
import aiosqlite


class APIHandler():
    database_instance = None
    server = None

    def __init__(self):
        pass

    def start(self):
        app = flask.Flask(__name__)
        app.config["DEBUG"] = False

        async def fetch_user_from_db(uuid: str):
            cursor: aiosqlite.Cursor = await DBConnection().get_db().cursor()

            await cursor.execute('''
                SELECT *
                FROM "BANNED"
                WHERE uuid=:uuid
            ''', {
                "uuid": uuid
            })
            res = await cursor.fetchone()
            await cursor.close()

            if res is None:
                return False

            return True

        @app.route('/banlist', methods=['GET'])
        def BannedAPI():
            uuid = request.args.get('uuid')

            isBanned = fetch_user_from_db(uuid)

            bannedState = {
                "UUID": uuid,
                "banned": isBanned
            }
            return jsonify(bannedState)

        app.run()

    def stop(self):
        pass

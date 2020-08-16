import asyncio
import logging
import os

import aiofiles
import configargparse
from aiohttp import web

CHUNK_SIZE = 100 * 1024


class Archivator:
    def __init__(self, throttling, path_to_files):
        self.throttling = throttling
        self.path_to_files = path_to_files

    async def get_archive(self, request):
        folder_name = request.match_info['archive_hash']
        archive_path = os.path.join(self.path_to_files, folder_name)

        if not os.path.exists(archive_path):
            raise web.HTTPNotFound(text="Архив не существует или был удален.")

        response = web.StreamResponse()
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = 'attachment; filename="{}.zip"'.format(folder_name)

        await response.prepare(request)

        proc = await asyncio.subprocess.create_subprocess_exec('zip', '-r', '-j', '-', archive_path, '>',
                                                               stdout=asyncio.subprocess.PIPE)
        try:
            while True:
                chunk = await proc.stdout.read(CHUNK_SIZE)
                if not chunk:
                    break

                logging.debug('Sending archive chunk ...')
                await response.write(chunk)

                if self.throttling:
                    await asyncio.sleep(1)

            return response
        except asyncio.CancelledError:
            logging.debug('Download was interrupted')
            proc.kill()
            raise
        except BaseException:
            proc.kill()
            raise
        finally:
            outs, errs = await proc.communicate()
            await response.write(outs)
            return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def get_env_params():
    parser = configargparse.ArgParser(default_config_files=['./config.conf'])
    parser.add_argument('-d', '--debug', action='store_true', help='If provided enable debug')
    parser.add_argument('-t', '--throttling', action='store_true', help='If provided enable sleep between batches')
    parser.add_argument('-p', '--path', help='Path to folder with data')

    args = parser.parse_args()
    throttling = args.throttling or os.environ.get('THROTTLING')
    path_to_files = args.path or os.environ.get('PATH_TO_FILES')

    if args.debug or os.environ.get('DEBUG'):
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    logging.basicConfig(level=logging_level)

    return throttling, path_to_files


if __name__ == '__main__':
    archivator = Archivator(*get_env_params())
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archivator.get_archive),
    ])
    web.run_app(app)

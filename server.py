import argparse
import asyncio
import logging
import os

import aiofiles
from aiohttp import web

CHUNK_SIZE = 100 * 1024


async def archivate(request):
    folder_name = request.match_info.get('archive_hash')
    archive_path = os.path.join(os.environ['PATH_TO_FILES'], folder_name)

    if not os.path.exists(archive_path):
        raise web.HTTPNotFound(text="Архив не существует или был удален.")

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/html'
    response.headers['Content-Disposition'] = 'attachment; filename="test.zip"'

    await response.prepare(request)

    proc = await asyncio.subprocess.create_subprocess_exec('zip', '-r', '-', archive_path, '>',
                                                           stdout=asyncio.subprocess.PIPE)
    try:
        while True:
            chunk = await proc.stdout.read(CHUNK_SIZE)
            if not chunk:
                break

            logging.debug('Sending archive chunk ...')
            await response.write(chunk)

            if os.environ['THROTTLING']:
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


def setup_env():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true', help='If provided enable debug')
    parser.add_argument('-t', '--throttling', action='store_true', help='If provided enable sleep between batches')
    parser.add_argument('-p', '--path',
                        help='Path to folder with data',
                        default=os.path.join(os.getcwd(), 'test_photos'))

    args = parser.parse_args()
    os.environ['THROTTLING'] = os.environ.get('THROTTLING') or str(args.throttling)
    os.environ['PATH_TO_FILES'] = os.environ.get('PATH_TO_FILES') or str(args.path)

    if os.environ.get('DEBUG') or args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


if __name__ == '__main__':
    setup_env()
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archivate),
    ])
    web.run_app(app)

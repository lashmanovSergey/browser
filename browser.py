import socket
import sys
import ssl
import datetime
import tkinter
import gzip
from pathlib import Path 

# Self-created functions
from instruments import parse_url
from instruments import layout
import cache

WIDTH, HEIGHT = 800, 600
SCROLL_STEP = 100
HSTEP, VSTEP = 13, 18

class Browser:
    def __init__(self):
        # browser settings
        self.user_agent = 'browser.py'

        self.scroll = 0

        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            height=HEIGHT,
            width=WIDTH
        )
        self.canvas.pack()
        self.display_list = []

        self.window.bind('<Down>', self.scrolldown)
        self.window.bind('<Up>', self.scrollup)

        self.default_request_headers = {
            'Connection': 'keep-alive'
        }

        self.entities = {
            '&lt;': '<',
            '&gt;': '>'
        }

        # browser feature to cache some pages based on cache-control header
        self.cache_dir = './cache/'
        self.cached_pages = {}

        # dictionary to keep alive connections
        self.connections = {}

        # dictionary to keep counter of redirects for each host
        self.redirects_loop_prevention = {}
        self.critical_number_of_redirects = 5

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()
    
    def scrollup(self, e):
        self.scroll = max(self.scroll - SCROLL_STEP, 0)
        self.draw()

    def process_url(self, url):
        parsed_url = parse_url(url)
        if parsed_url['scheme'] == 'http' or parsed_url['scheme'] == 'https':
            if url in self.cached_pages and self.cached_pages[url].isValid():
                print('[CONSOLE] Getting {} from cache'.format(url))
                self.show_content(self.cached_pages[url].getPage())
            else:
                self.make_request(url)
        elif parsed_url['scheme'] == 'file':
            self.load_filesystem(parsed_url)

    def load_filesystem(self, url):
        if url['host'] != '':
            return

        root_dir = Path('/')
        path = root_dir.joinpath(url['path'])

        if not path.exists():
            return

        if path.is_file():
            file = open(path, 'r')
            content = file.read()
            print(content)
        elif path.is_dir():
            for item in path.iterdir():
                print(item)

    def lex(self, content):
        # it takes content that shows without tags
        # and automatically replaces all entities with their values

        in_tag = False
        content_without_tags = ''

        # removing all tags
        for c in content:
            if c == '<':
                in_tag = True
            elif c == '>':
                in_tag = False
            elif in_tag == False:
                content_without_tags += c
        
        # entitiy replacement
        for entity, value in self.entities.items():
            while entity in content_without_tags:
                content_without_tags = content_without_tags.replace(entity, value)
        
        return content_without_tags
        
    
    def show_content(self, content):
        text = self.lex(content)
        self.display_list = layout(text, WIDTH)
        self.draw()
    
    def draw(self):
        self.canvas.delete('all')
        for x, y, c in self.display_list:

            if y > self.scroll + HEIGHT:
                continue
            if y + VSTEP < self.scroll:
                continue

            self.canvas.create_text(x, y - self.scroll, text=c)
            
            

    def make_request(self, url):

        parsed_url = parse_url(url)

        # creating request body
        r = 'GET /{} HTTP/1.1\r\n'.format(parsed_url['path'])
        r += 'Host: {}\r\n'.format(parsed_url['host'])
        r += 'Connection: {}\r\n'.format('keep-alive')
        r += 'User-Agent: {}\r\n'.format(self.user_agent)
        r += 'Accept-Encoding: {}\r\n'.format('gzip')
        r += '\r\n'

        # take already existed socket or create new one
        if parsed_url['host'] not in self.connections:
            s = self.create_socket(parsed_url)
            self.connections[parsed_url['host']] = s
        else:
            s = self.connections[parsed_url['host']]

        s.send(r.encode('utf-8'))

        with open('logs.txt', 'a') as logs:
            logs.write(f'[{str(datetime.datetime.now())}]\r\n')
            logs.write(r + '\r\n')

        response = s.makefile('rb', encoding='utf-8', newline='\r\n')
        status_line = response.readline().decode('utf-8')
        version, status, explanation = status_line.split(' ', 2)

        with open('logs.txt', 'a') as logs:
            logs.write(f'[{str(datetime.datetime.now())}]\r\n')
            logs.write(status_line)

        # read headers line by line and keep them in the dictionary
        response_headers = {}
        while True:
            line = response.readline().decode('utf-8')

            with open('logs.txt', 'a') as logs:
                logs.write(line)

            if line == '\r\n':
                break
            header_name, header_value = line.split(':', 1)
            response_headers[header_name.casefold()] = header_value.strip().casefold()

        response_headers['connection'] = response_headers['connection'] if 'connection' in response_headers else 'close'

        # if server wants to close connection we do it
        if response_headers['connection'] == 'close':
            self.connections[parsed_url['host']].close()
            self.connections.pop(parsed_url['host'])

        # process redirects
        if status == '301' or status == '302':
            self.follow_redirect(parsed_url['scheme'], parsed_url['host'], response_headers['location'])
            return

        # reading response body
        if 'content-length' in response_headers:
            content_length = int(response_headers['content-length'])
            body_bytes = response.read(content_length)
            
            # Decompressing of data
            if 'content-encoding' in response_headers and\
                'gzip' in response_headers['content-encoding']:
                body_bytes = gzip.decompress(body_bytes)

            body = body_bytes.decode('utf-8')

        elif 'transfer-encoding' in response_headers:
            body = ''
            while True:
                chunk_length_encoded = response.readline()
                chunk_length = int(chunk_length_encoded.decode('utf-8').strip(), 16)

                if chunk_length == 0:
                    break
                
                chunk_encoded = response.read(chunk_length + len('\r\n'))

                # Decompressing of data
                if 'content-encoding' in response_headers and\
                    'gzip' in response_headers['content-encoding']:
                    chunk_encoded = chunk_encoded.strip()
                    chunk_encoded = gzip.decompress(chunk_encoded)

                chunk = chunk_encoded.decode('utf-8')

                body += chunk
        
        # caching page for optimization
        if 'cache-control' in response_headers:
            cache_control = 'cache-control' + ':' + response_headers['cache-control']
        else:
            cache_control = 'cache-control' + ':' + 'no-cache'

        cached_page = cache.CachedPage(url, cache_control, body)
        self.cached_pages[url] = cached_page
        
        # update counter because we finished with redirects
        self.redirects_loop_prevention[parsed_url['host']] = 0

        self.show_content(body)
    
    def follow_redirect(self, scheme, host, url):
        if url.startswith('/'):
            url = scheme + '://' + host + url
        
        parsed_url = parse_url(url)

        assert parsed_url['scheme'] in ['https', 'http']

        if parsed_url['host'] in self.redirects_loop_prevention:
            self.redirects_loop_prevention[parsed_url['host']] += 1
        else:
            self.redirects_loop_prevention[parsed_url['host']] = 1
        
        if self.redirects_loop_prevention[parsed_url['host']] >= self.critical_number_of_redirects:
            return
        
        self.make_request(url)

    def create_socket(self, url):
        # returns created socket with established connection

        socket_address_family = socket.AF_INET
        socket_type = socket.SOCK_STREAM
        socket_proto = socket.IPPROTO_IP

        s = socket.socket(socket_address_family, socket_type, socket_proto)
        s.connect((url['host'], url['port']))

        # make transitions encrypted/secure
        if url['scheme'] == 'https':
            context = ssl.create_default_context()
            s = context.wrap_socket(s, server_hostname=url['host'])

        return s

if __name__ == "__main__":
    # Usage:
    # python browser.py <url>

    if (len(sys.argv) != 2):
        print('Usage: python browser.py <url>')
        exit()

    browser = Browser()
    browser.process_url(sys.argv[1])
    tkinter.mainloop()
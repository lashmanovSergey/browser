import socket
import sys
import ssl
from pathlib import Path 

# Self-created functions
from instruments import parse_url
import cache


class Browser:
    def __init__(self):
        # browser settings
        self.user_agent = 'browser.py'

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
            print('[CONSOLE] Cannot open other\'s filesystem')
            return

        root_dir = Path('/')
        path = root_dir.joinpath(url['path'])

        if not path.exists():
            print('[CONSOLE] Path does not exist')
            return

        if path.is_file():
            file = open(path, 'r')
            content = file.read()
            print(content)
        elif path.is_dir():
            for item in path.iterdir():
                print(item)
    
    def show_content(self, content):
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
        
        print(content_without_tags)

    def make_request(self, url):

        parsed_url = parse_url(url)

        # creating request body
        r = 'GET /{} HTTP/1.1\r\n'.format(parsed_url['path'])
        r += 'Host: {}\r\n'.format(parsed_url['host'])
        r += 'Connection: {}\r\n'.format('keep-alive')
        r += 'User-Agent: {}\r\n'.format(self.user_agent)
        r += '\r\n'

        # take already existed socket or create new one
        if parsed_url['host'] not in self.connections:
            s = self.create_socket(parsed_url)
            self.connections[parsed_url['host']] = s
            print('[CONSOLE] New connection to {} has been established'.format(parsed_url['host']))
        else:
            s = self.connections[parsed_url['host']]
            print('[CONSOLE] Connection with {} has been established'.format(parsed_url['host']))

        s.send(r.encode('utf-8'))
        print('[CONSOLE] Request has been sent to {}'.format(parsed_url['host']))

        response = s.makefile('rb', encoding='utf-8', newline='\r\n')
        print('[CONSOLE] Successfully got response from {}'.format(parsed_url['host']))

        status_line = response.readline().decode('utf-8')
        version, status, explanation = status_line.split(' ', 2)
        print('[CONSOLE] {} {} {}'.format(version, status, explanation))

        # read headers line by line and keep them in the dictionary
        response_headers = {}
        while True:
            line = response.readline().decode('utf-8')
            if line == '\r\n':
                break
            header_name, header_value = line.split(':', 1)
            response_headers[header_name.casefold()] = header_value.strip().casefold()

        response_headers['connection'] = response_headers['connection'] if 'connection' in response_headers else 'close'

        # if server wants to close connection we do it
        if response_headers['connection'] == 'close':
            self.connections[parsed_url['host']].close()
            self.connections.pop(parsed_url['host'])

        if status == '301': # process redirects
            self.follow_redirect(parsed_url['scheme'], parsed_url['host'], response_headers['location'])
            return

        # reading response body
        if 'content-length' in response_headers:
            content_length = int(response_headers['content-length'])
            body_bytes = response.read(content_length)
            body = body_bytes.decode('utf-8')
        elif 'transfer-encoding' in response_headers:
            body = ''
            while True:
                chunk_length_encoded = response.readline()
                chunk_length = int(chunk_length_encoded.decode('utf-8').strip(), 16)

                if chunk_length == 0:
                    break
                
                chunk_encoded = response.read(chunk_length + len('\r\n'))
                chunk = chunk_encoded.decode('utf-8')

                body += chunk
        
        # caching page for optimization
        if 'cache-control' in response_headers:
            print('[CONSOLE] Caching {}'.format(url))
            cache_control = 'cache-control' + ':' + response_headers['cache-control']
        else:
            cache_control = 'cache-control' + ':' + 'no-cache'

        cached_page = cache.CachedPage(url, cache_control, body)
        self.cached_pages[url] = cached_page
        
        # update counter because we finished with redirects
        self.redirects_loop_prevention[parsed_url['host']] = 0

        self.show_content(body)
    
    def follow_redirect(self, scheme, host, url):
        print('[CONSOLE] Following redirect to {}'.format(url))

        if url.startswith('/'):
            url = scheme + '://' + host + url
        
        parsed_url = parse_url(url)

        assert parsed_url['scheme'] in ['https', 'http']

        if parsed_url['host'] in self.redirects_loop_prevention:
            self.redirects_loop_prevention[parsed_url['host']] += 1
        else:
            self.redirects_loop_prevention[parsed_url['host']] = 1
        
        if self.redirects_loop_prevention[parsed_url['host']] >= self.critical_number_of_redirects:
            print('[CONSOLE] Do not follow redirects due to security')
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

    browser = Browser()
    browser.process_url(sys.argv[1])
    browser.process_url(sys.argv[1])
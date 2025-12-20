from instruments import parse_url
from instruments import parse_header
import time

# This class was created for cache implementation

class CachedPage:
    def __init__(self, url, cache_control, content):
        self.url = url
        self.cache_control = parse_header(cache_control)
        self.content = content

        self.start_time = time.time()

        self.max_age = 0
        self.no_cache = False
        
        for i in range(len(self.cache_control['cache-control'])):
            item = self.cache_control['cache-control'][i]
            if 'max-age' in item:
                self.max_age = int(item['max-age'])
            if 'no-cache' == item:
                self.no_cache = True
        
        self.end_time = self.start_time + self.max_age
    
    def isValid(self) -> bool:
        current_time = time.time()

        if self.no_cache:
            return False

        if current_time > self.end_time:
            return False

        return True
    
    def getPage(self) -> str:
        return self.content
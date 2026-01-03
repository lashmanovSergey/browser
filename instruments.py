# To keep some specific functions that can help in implementation

def parse_url(url):
    # returns dictionary with the following keys:
    # 1. scheme
    # 2. host
    # 3. port
    # 4. path

    scheme, authority = url.split('://')
    host, path = authority.split('/', 1)

    if scheme == 'http':
        port = 80
    elif scheme == 'https':
        port = 443
    else:
        port = 8080
    
    if ':' in host:
        host, port = host.split(':', 1)
    
    return {
        'scheme': scheme,
        'host': host,
        'port': int(port),
        'path': path
    }

def parse_header(header):
    # Lets consider the following header:
    # Cache-Control: max-age, public
    #
    # It parses this one to the following structure:
    # {'Cache-Control': ['max-age': 15, 'public']}

    header_name, header_values = header.split(':', 1)

    header_values = header_values.split(',')
    
    values = []

    for item in header_values:
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            values += [{key: value}]
        else:
            values += [item]
    
    return {
        header_name: values
    }

def layout(text, width, h_step = 13, v_step = 18):
    display_list = []
    cursor_x, cursor_y = h_step, v_step

    for c in text:
        display_list.append((cursor_x, cursor_y, c))
        cursor_x += h_step

        # Provides dynamic line text showing
        if cursor_x >= width - h_step:
            cursor_x = h_step
            cursor_y += v_step

    return display_list
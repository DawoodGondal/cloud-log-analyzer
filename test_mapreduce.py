from mapreduce import run_mapreduce

if __name__ == '__main__':
    lines = [
        '127.0.0.1 - - [01/Jan/2024:14:32:01 +0000] "GET /index.html HTTP/1.1" 200 1234',
        '127.0.0.1 - - [01/Jan/2024:14:45:01 +0000] "GET /missing HTTP/1.1" 404 512',
        '192.168.1.1 - - [01/Jan/2024:15:10:01 +0000] "POST /api HTTP/1.1" 500 256',
        '10.0.0.1 - - [01/Jan/2024:15:22:01 +0000] "GET /page HTTP/1.1" 404 128',
        '10.0.0.2 - - [01/Jan/2024:16:05:01 +0000] "GET /admin HTTP/1.1" 403 64',
    ]

    with open('test.log', 'w') as f:
        f.write('\n'.join(lines))

    print("test.log created!")
    result = run_mapreduce('test.log')
    print("ERRORS:", result['errors'])
    print("TRAFFIC:", result['traffic'])
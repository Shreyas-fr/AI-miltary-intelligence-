import random
import string

def generate_dga(length):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

tlds = ['.com', '.net', '.org', '.info', '.biz', '.ru', '.cn', '.cc']
with open('dns-threat-filter/api/data/malicious_domains.txt', 'w') as f:
    for _ in range(10000):
        length = random.randint(8, 20)
        domain = generate_dga(length) + random.choice(tlds)
        f.write(domain + '\n')

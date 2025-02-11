import time, sha3, requests, json
from termcolor import colored


siriAddress = "0x4baE9F81a30b148Eb40044F6268B5496861Cb313"
poolURL = "http://168.138.151.204/poolsiri/"

hashes_per_list = 1024
hashrateRefreshRate = 25 # Secconds

def formatHashrate(hashrate):
    if hashrate < 1000:
        return f"{round(hashrate, 2)} H/s"
    elif hashrate < 1000000:
        return f"{round(hashrate/1000, 2)} kH/s"
    elif hashrate < 1000000000:
        return f"{round(hashrate/1000000, 2)} MH/s"
    elif hashrate < 1000000000000:
        return f"{round(hashrate/1000000000, 2)} GH/s"

class pool:

    def login():
        return requests.post(poolURL, json={'id': None, 'method': 'mining.authorize', 'params': [siriAddress]}).json()["id"]

    def requestJob(id):
        response = requests.post(poolURL, json={'id': id, 'method': 'mining.subscribe', 'params': ['ESP8266']}).json()["params"]
        return {"JOB_ID": response[0], "lastBlockHash": response[1], "target": response[2], "startNonce": response[3], "EndNonce": response[4], "timestamp": response[7], "PoolAddr": response[9]}

    def submit(id, jobID, proof, timestamp, nonce):
        response = requests.post(poolURL, json={"id": id, "method": "mining.submit", "params": [siriAddress, jobID, proof, timestamp, nonce]}).json()
        return {"Accepted": response["result"], "TXID": response["raw"]}

class console_log:

    def rgbPrint(string, color):
        print(colored(str(string), color))
    
    def logged_in(id):
        console_log.rgbPrint("Logged in as: " + siriAddress + "@" + poolURL + ", ID: " + str(id), "cyan")

    def share(type, data):
        if data["Accepted"]:
            if data["TXID"]:
                console_log.rgbPrint(type + " accepted, TXID: " + json.loads(data["TXID"])["result"][0], "green")
            else:
                console_log.rgbPrint(type + " accepted, pool dry", "yellow")
        else:
            console_log.rgbPrint(type + " rejected", "red")
    
    def hashrate(hashrates):
        console_log.rgbPrint("Hashrate: " + formatHashrate(sum(hashrates)/len(hashrates)), "cyan")



def beaconRoot(lastBlockHash, timestamp, poolAddr):
    messagesHash = b'\xef\xbd\xe2\xc3\xae\xe2\x04\xa6\x9bv\x96\xd4\xb1\x0f\xf3\x117\xfex\xe3\x94c\x06(O\x80n-\xfch\xb8\x05' # Messages hash is constant, no need to hash it everytime
    bRoot = sha3.keccak_256(bytes.fromhex(lastBlockHash.replace("0x", "")) + int(timestamp).to_bytes(32, 'big') + messagesHash + bytes.fromhex(poolAddr.replace("0x", ""))).digest()
    return bRoot


def PoW(bRoot, start_nonce, end_nonce, target):   
    target = int(target, 16) 
    nonce = start_nonce

    bRoot_hashed = sha3.keccak_256(bRoot)
    bRoot_hashed.update((0).to_bytes(24, "big"))

 
    start = time.time()
    hashes = []

    while True:

        for i in range (hashes_per_list):
            finalHash = bRoot_hashed.copy()
            finalHash.update(nonce.to_bytes(32, "big"))
            hashes.append(finalHash)
            nonce +=1

        for hash in hashes:
            if (int.from_bytes(hash.digest(), "big") < target):
                validNonce = (nonce - (len(hashes) - hashes.index(hash)))
                return True, {"Nonce": validNonce, "Proof": "0x" + hash.hexdigest(), "Hashrate": (nonce - start_nonce) / (time.time() - start)}

        if nonce > end_nonce:
            return False, {"Hashrate": (nonce - start_nonce) / (time.time() - start)}

        hashes = []

        



id = pool.login()
console_log.logged_in(id)

startTime = time.time()
hashrates = []

while True:
    job = pool.requestJob(id)
    bRoot = beaconRoot(job["lastBlockHash"], job["timestamp"], job["PoolAddr"])
    FinalHash = PoW(bRoot, job["startNonce"], job["EndNonce"], job["target"])

    if not FinalHash[0]:
        hashrates.append(FinalHash[1]["Hashrate"])
        console_log.share("Share", pool.submit(id, job["JOB_ID"], "0x00", job["timestamp"], 1))

    if FinalHash[0]:
        hashrates.append(FinalHash[1]["Hashrate"])
        console_log.rgbPrint("Block found, submiting to pool", "magenta")
        console_log.share("Block", pool.submit(id, job["JOB_ID"], FinalHash[1]["Proof"], job["timestamp"], FinalHash[1]["Nonce"]))

    if time.time() - startTime > hashrateRefreshRate:   
        console_log.hashrate(hashrates)
        hashrates = []
        startTime = time.time()  

    time.sleep(2.5)

import hashlib
import json
import time
from uuid import uuid4
from urllib.parse import urlparse

import requests
from flask import Flask, json, request


class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        # Create a genesis block
        self.new_block(proof=100, previous_hash=1)

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proof, previous_hash=None):
        """
        Creates a new block and adds it to the blockchain
        :param proof: <str> The proof returned by the PoW algorithm
        :param previous_hash: (Optional) <str> The hash of the previous block
        :return: <dict> New block
        """
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.current_transactions,
            'previous_hash': previous_hash or hash(self.chain[-1]),
            'proof': proof,
        }
        # Reset the current list of transactions
        self.current_transactions = []
        self.chain.append(block)

        return block

    def new_transaction(self, sender, receiver, amount):
        """
        Creates a new transaction to go into the next mined block
        :param sender: <str> Address of the sender
        :param receiver: <str> Address of the receiver
        :param amount: <int> Amount
        :return: <int> The index of the block that will hold this transaction
        """

        self.current_transactions.append({
            'sender': sender,
            'receiver': receiver,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    def valid_chain(self, chain):
        """
        Determines if a given blockchain is valid
        :param chain: <str> The blockchain
        :return: <bool>
        """

        last_block = chain[0]
        current_index = 1
        print(f'{last_block}')
        print('/n----------/n')
        while current_index < len(chain):
            current_block = chain[current_index]
            print(f'{current_block}')
            print('/n----------/n')

            # Verify the BlockHash
            if hash(last_block) != current_block['previous_hash']:
                return False

            # Verify PoW
            if not self.valid_proof(last_proof=last_block['proof'], proof=current_block['proof']):
                return False

            last_block = current_block
            current_index += 1

        return True

    def resolve_conflict(self):
        """
        Consensus algorithm to maintain the longest valid chain on all the nodes
        :return: <bool> Returns if chain has been replaced or not
        """

        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            length = response.json()['length']
            chain = response.json()['chain']

            if length > max_length:
                if self.valid_chain(chain):
                    new_chain = chain
                    max_length = length

        if new_chain is None:
            return False

        self.chain = new_chain

        return True

    @staticmethod
    def hash(block):
        """
        Creates a sha256 hash of the block
        :param block: <dict> Block
        :return: <str> Hash of the Block
        """
        # The Dictionary should be ordered, else the hashes will be inconsistent
        block_string = json.dumps(block, sort_keys=True).encode()
        hash_of_block = hashlib.sha256(block_string).hexdigest()

        return hash_of_block

    @property
    def last_block(self):
        # Returns the last block
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """
        Validates the proof
        Computes the proof p such that
            - When p is multiplied by the previous proof we get 4 leading zeros
        :param last_proof: <str> The previous block proof
        :return: <str> The proof
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        hash_of_proof = hashlib.sha256(guess).hexdigest()
        return hash_of_proof[:4] == "0000"


# Instantiate our Node
app = Flask(__name__)

# Generate a unique identifier for the node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values['nodes']

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': f'{len(nodes)} have been registered',
        'total_nodes': f'{len(nodes)}'
    }

    return json.jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflict()

    if replaced:
        response = {
            'message': f'The chain has been replaced',
            'new chain': f'{blockchain.chain}'
        }
    else:
        response = {
            'message': f'The chain is valid',
            'new chain': f'{blockchain.chain}'
        }

    return json.jsonify(response), 200


@app.route('/mine', methods=['GET'])
def mine():
    """
    Calculate PoW, Get a reward, Add block to the chain
    :return:
    """
    last_block = blockchain.last_block
    last_proof = last_block['proof']

    proof = blockchain.proof_of_work(last_proof)
    # reward
    blockchain.new_transaction(
        sender="0",
        receiver=node_identifier,
        amount=1)

    previous_hash = last_block['previous_hash']
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return json.jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'receiver', 'amount']

    if not all(k in values for k in required):
        return 'Missing values', 400

    index = blockchain.new_transaction(sender=values['sender'], receiver=values['receiver'], amount=values['amount'])
    response = {'message': f'Transaction will be added to block number {index}'}

    return json.jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return json.jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

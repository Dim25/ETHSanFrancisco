from flask import Flask, request
app = Flask(__name__)

import json
import web3

from web3 import Web3, HTTPProvider, TestRPCProvider
from solc import compile_source
from web3.contract import ConciseContract

import pprint
pp = pprint.PrettyPrinter(indent=4)

# Solidity
# ========
# Based on: https://solidity.readthedocs.io/en/v0.4.24/solidity-by-example.html#safe-remote-purchase
safe_purchase_source_code = '''
pragma solidity ^0.4.22;

contract Purchase {
    uint public value;
    address public seller;
    address public buyer;
    address public trustparty;
    enum State { Created, Locked, Inactive }
    State public state;
    // address[] deposits;

    uint public a1value;
    uint public b1value;
    uint public c1value;

    // Ensure that `msg.value` is an even number.
    // Division will truncate if it is an odd number.
    // Check via multiplication that it wasn't an odd number.
    constructor() public payable {
        seller = msg.sender;
        value = msg.value / 2;
        require((2 * value) == msg.value, "Value has to be even.");
    }

    modifier condition(bool _condition) {
        require(_condition);
        _;
    }

    modifier onlyBuyer() {
        require(
            msg.sender == buyer,
            "Only buyer can call this."
        );
        _;
    }

    modifier onlySeller() {
        require(
            msg.sender == seller,
            "Only seller can call this."
        );
        _;
    }

    modifier onlyTrustParty() {
        require(
            msg.sender == trustparty,
            "Only trustparty can call this."
        );
        _;
    }

    modifier inState(State _state) {
        require(
            state == _state,
            "Invalid state."
        );
        _;
    }

    event Aborted();
    event PurchaseConfirmed();
    event ItemReceived();

    /// Abort the purchase and reclaim the ether.
    /// Can only be called by the seller before
    /// the contract is locked.
    function abort()
        public
        onlySeller
        inState(State.Created)
    {
        emit Aborted();
        state = State.Inactive;
        seller.transfer(address(this).balance);
    }

    /// Confirm the purchase as buyer.
    /// Transaction has to include `2 * value` ether.
    /// The ether will be locked until confirmReceived
    /// is called.
    function confirmPurchase()
        public
        inState(State.Created)
        condition(msg.value == (2 * value))
        payable
    {
        emit PurchaseConfirmed();
        buyer = msg.sender;
        state = State.Locked;
    }

    /// Confirm that you (the buyer) received the item.
    /// This will release the locked ether.
    function confirmReceived()
        public
        onlyBuyer
        inState(State.Locked)
    {
        emit ItemReceived();
        // It is important to change the state first because
        // otherwise, the contracts called using `send` below
        // can call in again here.
        state = State.Inactive;

        // NOTE: This actually allows both the buyer and the seller to
        // block the refund - the withdraw pattern should be used.

        buyer.transfer(value);
        seller.transfer(address(this).balance);
    }

    /// Define contract
    /// Side A1 - buyer
    function defineContractA1(address _aida) public {
        buyer = _aida;
        // if (compareAddress(_aida,msg.sender)) {
        //     greeting = "compare1-True";
        // }
    }

    /// Side B1 - seller
    function defineContractB1(address _aida) public {
        seller = _aida;
        // if (compareAddress(_aida,msg.sender)) {
        //     greeting = "compare1-True";
        // }
    }    

    /// Side C1 - trustparty / arbitration
    function defineContractC1(address _aida) public {
        trustparty = _aida;
        // if (compareAddress(_aida,msg.sender)) {
        //     greeting = "compare1-True";
        // }
    }


    function sideA1() constant returns (address) {
        return buyer;
    }

    function sideB1() constant returns (address) {
        return seller;
    }

    function sideC1() constant returns (address) {
        return trustparty;
    }    


    function sideA1value() constant returns (uint) {
        return a1value;
    }

    function sideB1value() constant returns (uint) {
        return b1value;
    }

    function sideC1value() constant returns (uint) {
        return c1value;
    }


    function depositA1() payable {
      // deposits[msg.sender] += msg.value;
      a1value += msg.value;
    }

    function pay_a1tob1() {
      // deposits[msg.sender] += msg.value;
      // a1value += msg.value;
      // seller.transfer(a1value.balance);


      // seller.transfer(a1value);
      seller.transfer(address(this).balance);
    }

    function payToB1() constant returns (address) {
        seller.send(100000);
        // seller.transfer(a1value/2);
        // seller.transfer(address(this).balance/2);
        // return address(this).balance;
        return address(this); // 0x8a13c30E459a3660b139441E4B52dE2Dc9D4a1Aa
    }

    function contractAddress() constant returns (address) {
        return address(this);
    }

    function contractBalance() constant returns (uint) {
        return address(this).balance;
    }


}
'''

def get_balances(w3,wallets_data):
    step_data = []
    for k,account in enumerate(w3.eth.accounts):
        step_data.append({
            "id":k,
            "account":account,
            "balance":w3.eth.getBalance(account)
            })

    wallets_data.append(step_data)
    return wallets_data



@app.route('/', methods=["GET","POST"])
def pipeline():
    buyer = request.form.get('buyer')
    seller = request.form.get('seller')
    trustparty = request.form.get('trustparty')

    print("buyer",buyer)
    print("seller",seller)
    print("trustparty",trustparty)

    # TODO: work with exceptions


    safe_purchase_compiled_sol = compile_source(safe_purchase_source_code) # Compiled source code
    safe_purchase_contract_interface = safe_purchase_compiled_sol['<stdin>:Purchase']

    w3 = Web3(TestRPCProvider())
    wallets_data = []

    wallets_data = get_balances(w3,wallets_data)
    print(wallets_data)

    # Instantiate and deploy contracts
    safe_purchase_contract = w3.eth.contract(abi=safe_purchase_contract_interface['abi'], bytecode=safe_purchase_contract_interface['bin'])


    safe_purchase_tx_hash = safe_purchase_contract.deploy(transaction={'from': buyer, 'gas': 4000000})
    wallets_data = get_balances(w3,wallets_data)


    safe_purchase_tx_receipt = w3.eth.getTransactionReceipt(safe_purchase_tx_hash)
    safe_purchase_contract_address = safe_purchase_tx_receipt['contractAddress']
    print("safe_purchase_contract_address",safe_purchase_contract_address)



    safe_purchase_abi = safe_purchase_contract_interface['abi']
    print("safe_purchase_abi:")
    pp.pprint(safe_purchase_abi)
    safe_purchase_contract_instance = w3.eth.contract(address=safe_purchase_contract_address, abi=safe_purchase_abi,ContractFactoryClass=ConciseContract)


    print('-'*80)
    print('[safe_purchase]')
    # print('New Contract: {}'.format(factory_contract_instance.createContract("0xd6F084Ee15E38c4f7e091f8DD0FE6Fe4a0E203Ef")))
    safe_purchase_contract_instance.defineContractA1(buyer, transact={'from': buyer})
    safe_purchase_contract_instance.defineContractB1("0xDCEceAF3fc5C0a63d195d69b1A90011B7B19650D", transact={'from': buyer})
    safe_purchase_contract_instance.defineContractC1(trustparty, transact={'from': buyer})

    wallets_data = get_balances(w3,wallets_data)


    print('-'*80)
    print('A1: {}'.format(safe_purchase_contract_instance.sideA1()))
    print('A1 value: {}'.format(safe_purchase_contract_instance.sideA1value()))
    print('B1: {}'.format(safe_purchase_contract_instance.sideB1()))
    print('B1 value: {}'.format(safe_purchase_contract_instance.sideB1value()))
    print('C1: {}'.format(safe_purchase_contract_instance.sideC1()))
    print('C1 value: {}'.format(safe_purchase_contract_instance.sideC1value()))


    safe_purchase_contract_instance.depositA1(transact={'from': buyer, 'value': 1000000000000000000000})
    wallets_data = get_balances(w3,wallets_data)



    print('contractAddress: {}'.format(safe_purchase_contract_instance.contractAddress()))
    print('contractBalance: {}'.format(safe_purchase_contract_instance.contractBalance()))


    # Pay right away
    safe_purchase_contract_instance.pay_a1tob1(transact={'from': buyer})
    wallets_data = get_balances(w3,wallets_data)

    print('B1: {}'.format(safe_purchase_contract_instance.sideB1()))


    print('contractAddress: {}'.format(safe_purchase_contract_instance.contractAddress()))
    print('contractBalance: {}'.format(safe_purchase_contract_instance.contractBalance()))

    return "Hello, ETH:SF, Let's #BUIDL ! Contract created: " + str(safe_purchase_contract_instance.contractAddress())


if __name__ == '__main__':
    app.run()

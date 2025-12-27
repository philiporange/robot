def fizzbuzz():
    """
    Prints numbers from 1 to 100, replacing:
    - Multiples of 3 with "Fizz"
    - Multiples of 5 with "Buzz"
    - Multiples of both with "FizzBuzz"
    """
    for num in range(1, 101):
        # Check for multiples of both 3 and 5 first
        if num % 3 == 0 and num % 5 == 0:
            print("FizzBuzz")
        # Then check for multiples of 3
        elif num % 3 == 0:
            print("Fizz")
        # Then check for multiples of 5
        elif num % 5 == 0:
            print("Buzz")
        # Otherwise, print the number
        else:
            print(num)

if __name__ == "__main__":
    fizzbuzz()

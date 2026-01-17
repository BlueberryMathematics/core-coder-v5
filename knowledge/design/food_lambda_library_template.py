"""
Lambda Function Library Template - EXPLAINED
A super clear example showing how lambda dictionaries work for organizing functions.
"""


class RecipeLibrary:
    """
    Think of this like a recipe book where you can select different recipes.
    Each recipe takes ingredients (inputs) and produces food (outputs).
    """
    
    def __init__(self):
        """Initialize the recipe library."""
        pass
    
    # Example Recipe Functions
    # -----------------------------------------------------------------------------------------------------------------
    def make_smoothie(self, fruit, size):
        """
        Makes a smoothie.
        
        Args:
            fruit: What fruit to use (the VARIABLE input)
            size: 'small' or 'large' (the FIXED setting)
            
        Returns:
            A string describing your smoothie
        """
        if size == 'small':
            return f"Here's a small {fruit} smoothie!"
        else:
            return f"Here's a LARGE {fruit} smoothie!"
    
    # -----------------------------------------------------------------------------------------------------------------
    def make_sandwich(self, filling, size):
        """
        Makes a sandwich.
        
        Args:
            filling: What filling to use (the VARIABLE input)
            size: 'small' or 'large' (the FIXED setting)
            
        Returns:
            A string describing your sandwich
        """
        if size == 'small':
            return f"Here's a small {filling} sandwich."
        else:
            return f"Here's a LARGE {filling} sandwich!"
    
    # -----------------------------------------------------------------------------------------------------------------
    def make_salad(self, veggie, size):
        """
        Makes a salad.
        
        Args:
            veggie: What veggie to use (the VARIABLE input)
            size: 'small' or 'large' (the FIXED setting)
            
        Returns:
            A string describing your salad
        """
        if size == 'small':
            return f"Here's a small {veggie} salad."
        else:
            return f"Here's a LARGE {veggie} salad!"
    
    # Lambda Function Library
    # -----------------------------------------------------------------------------------------------------------------
    def get_recipe_menu(self, size):
        """
        Creates a menu of recipes where SIZE is already decided.
        You just need to pick WHAT INGREDIENT later.
        
        Args:
            size: 'small' or 'large' - THIS GETS LOCKED IN NOW
            
        Returns:
            A lambda function that only needs the ingredient
        """
        
        print(f"\n{'='*60}")
        print(f"CREATING MENU WITH SIZE = '{size}'")
        print(f"{'='*60}")
        print("When you pick a recipe, the SIZE is already decided.")
        print("You'll only need to provide the INGREDIENT when you order.\n")
        
        # THIS IS THE KEY PART - THE LAMBDA DICTIONARY
        # ---------------------------------------------
        # 'ingredient' is a PLACEHOLDER - it waits for a value
        # 'size' is CAPTURED NOW - it's locked in from the parameter above
        
        recipes = {
            '1': lambda ingredient: self.make_smoothie(ingredient, size),
            '2': lambda ingredient: self.make_sandwich(ingredient, size),
            '3': lambda ingredient: self.make_salad(ingredient, size),
        }
        
        # Menu descriptions
        menu = {
            '1': 'Smoothie',
            '2': 'Sandwich', 
            '3': 'Salad',
        }
        
        # Display menu
        print("RECIPE MENU:")
        print("-" * 60)
        for key, name in menu.items():
            print(f'{key}: {name} (size is already set to "{size}")')
        print("-" * 60)
        
        # Get user selection
        while True:
            choice = input('Pick a recipe number (or "q" to quit): ')
            
            if choice.lower() == 'q':
                return None
                
            if choice in recipes:
                print(f"\n✓ You selected: {menu[choice]}")
                print(f"✓ Size is locked in as: {size}")
                print("✓ Now you can call this recipe with different ingredients!\n")
                return recipes[choice]
            else:
                print("Invalid choice. Try again.")


# ============================================================================
# DETAILED WALKTHROUGH - HOW IT WORKS
# ============================================================================

if __name__ == "__main__":
    
    print("\n" + "="*60)
    print("LAMBDA ARGUMENTS - STEP BY STEP WALKTHROUGH")
    print("="*60)
    
    # STEP 1: Create the library
    print("\nSTEP 1: Create a RecipeLibrary")
    print("-" * 60)
    library = RecipeLibrary()
    print("✓ Library created")
    
    # STEP 2: Get a recipe with SIZE pre-configured
    print("\n\nSTEP 2: Call get_recipe_menu(size='large')")
    print("-" * 60)
    print("What happens: 'large' gets CAPTURED by the lambda")
    print("Result: You get back a function that ONLY needs an ingredient")
    
    selected_recipe = library.get_recipe_menu(size='large')
    
    if not selected_recipe:
        exit()
    
    # STEP 3: Use the recipe with different ingredients
    print("\nSTEP 3: Call the recipe with different ingredients")
    print("-" * 60)
    print("The recipe ALREADY KNOWS size='large'")
    print("You just provide the ingredient each time:\n")
    
    print("Calling: selected_recipe('banana')")
    result1 = selected_recipe('banana')
    print(f"→ {result1}\n")
    
    print("Calling: selected_recipe('strawberry')")
    result2 = selected_recipe('strawberry')
    print(f"→ {result2}\n")
    
    print("Calling: selected_recipe('mango')")
    result3 = selected_recipe('mango')
    print(f"→ {result3}\n")
    
    # VISUAL EXPLANATION
    print("\n" + "="*60)
    print("VISUAL EXPLANATION OF WHAT HAPPENED")
    print("="*60)
    print("""
When you wrote:
    recipes = {
        '1': lambda ingredient: self.make_smoothie(ingredient, size),
    }

And called:
    selected_recipe = library.get_recipe_menu(size='large')

The lambda became:
    lambda ingredient: self.make_smoothie(ingredient, 'large')
                                                        ^^^^^^
                                                    'size' is now 'large'!

Then when you called:
    selected_recipe('banana')

It executed:
    self.make_smoothie('banana', 'large')
                        ^^^^^^    ^^^^^^
                    ingredient    size
                    (you provide) (already set)
    """)
    
    # COMPARE WITH DIFFERENT SIZE
    print("\n" + "="*60)
    print("COMPARISON: SAME RECIPE, DIFFERENT SIZE SETTING")
    print("="*60)
    
    library2 = RecipeLibrary()
    print("\nNow let's get the SAME recipe type but with size='small':\n")
    
    small_recipe = library2.get_recipe_menu(size='small')
    
    if small_recipe:
        print("\nUsing the small version:")
        result_small = small_recipe('banana')
        print(f"→ {result_small}")
        
        print("\nNotice the difference!")
        print(f"Large version: {result1}")
        print(f"Small version: {result_small}")
        print("\nSame ingredient ('banana'), different SIZE setting!")
    
    # FINAL SUMMARY
    print("\n" + "="*60)
    print("KEY TAKEAWAY")
    print("="*60)
    print("""
Lambda arguments work in TWO stages:

1. CAPTURED variables (from outer scope):
   - Set when the lambda is CREATED
   - Example: 'size' in get_recipe_menu(size='large')
   - These stay FIXED for the life of that lambda

2. PARAMETER variables (in the lambda definition):
   - Set when the lambda is CALLED
   - Example: 'ingredient' in lambda ingredient: ...
   - These change EVERY TIME you call the lambda

Think of it like:
    - CAPTURED = configuration/settings (set once)
    - PARAMETER = data/input (changes each call)
    """)
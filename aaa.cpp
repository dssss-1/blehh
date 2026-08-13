#include <iostream>

class Animal {
public:
    virtual void sound() {
        std::cout << "Some generic animal sound" << std::endl;
    }
};

class Dog : public Animal {
public:
    void sound() override {
        std::cout << "Woof!" << std::endl;
    }
};

int main() {
    Dog dog;
    Animal* animal = &dog;  // Use a pointer to access the derived class object
    animal->sound();  // This should call the overridden method in Dog

    return 0;
}
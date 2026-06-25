CXX ?= c++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -pedantic

BUILD_DIR := build
TARGET := $(BUILD_DIR)/meshfix_cpp
SRC := meshfix_cpp.cpp

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	mkdir -p $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(SRC) -o $(TARGET)

clean:
	rm -rf $(BUILD_DIR)
